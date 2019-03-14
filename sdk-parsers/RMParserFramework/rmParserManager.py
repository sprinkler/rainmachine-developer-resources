import os, sys, shutil
import imp
import time, copy

from pprint import pprint

from RMParserFramework.rmParser import RMParser

from RMDataFramework.rmForecastInfo import RMForecastInfo
from RMDataFramework.rmParserConfig import RMParserConfig

from RMDatabaseFramework.rmDatabaseManager import globalDbManager
from RMDatabaseFramework.rmParserDataTable import *
from RMDatabaseFramework.rmForecastInfoTable import RMForecastTable
from RMDatabaseFramework.rmUserDataTypeTable import RMUserDataTypeTable
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *

from RMDataFramework.rmMainDataRecords import RMNotification

from RMDataFramework.rmUserSettings import globalSettings

class RMParserManager:

    IGNORE_PYC_MODULES = True

    instance = None

    def __init__(self):
        RMParserManager.instance = self

        self.parsers = {}

        self.forceParsersRun = False
        self.__maxFails = 100
        self.__minDelayBetweenFails = 120 # 2 min
        self.__maxDelayBetweenFails = 300 # 5 min
        self.__stepDelayBetweenFails = 30 # 30 seconds
        self.__delayAfterMaxFails = 86400 # 1 day

        self.__lastRunningTimestamp = None # The timestamp when parsers last attempted to run
        self.__lastUpdateTimestamp = 0 # The timestamp when parsers actually ran
        self.__runningInterval = 60 # 1 minute


        self.parserTable = RMParserTable(globalDbManager.parserDatabase)
        self.parserDataTable = RMParserDataTable(globalDbManager.parserDatabase)
        self.forecastTable = RMForecastTable(globalDbManager.parserDatabase)
        self.userDataTypeTable = RMUserDataTypeTable(globalDbManager.parserDatabase)
        self.parserUserDataTypeTable = RMParserUserDataTable(globalDbManager.parserDatabase)

        self.userDataTypeTable.buildCache()

        self.mixer = None

        self.__load(os.path.dirname(__file__) + '/parsers')


    def preRun(self):
        unmixedForecastAvailable = False

        lastForecast = None
        latestForecastByParser = self.parserDataTable.getLastForecastByParser()
        for parserID in latestForecastByParser:
            parserConfig = self.findParserConfig(parserID)
            if parserConfig != None:
                parserConfig.runtimeLastForecastInfo = latestForecastByParser[parserID]
                if not parserConfig.runtimeLastForecastInfo.processed:
                    unmixedForecastAvailable = True
                if lastForecast == None:
                    lastForecast = parserConfig.runtimeLastForecastInfo

        log.debug("*** All values are already mixed! No need to run the Mixer!")

        for parserConfig in self.parsers:
            self.parserDataTable.clearHistory(parserConfig.dbID, False)
        globalDbManager.parserDatabase.commit()
        globalDbManager.parserDatabase.vacuum()

        return None, None

    def run(self, parserId = None, forceRunParser = False, forceRunMixer = False):
        currentTimestamp = rmCurrentTimestamp()
        forceRunParser = True

        if not forceRunParser and self.__lastRunningTimestamp is not None and (currentTimestamp - self.__lastRunningTimestamp) < self.__runningInterval:
            # We want to run the parser only each N minutes. This condition is not met, try later.
            log.debug("Parser %r not run lastRunning timestamp %s current %s" % (parserId, self.__lastRunningTimestamp, currentTimestamp))
            return None, None

        self.__lastRunningTimestamp = currentTimestamp

        newValuesAvailable = False
        newForecast = RMForecastInfo(None, currentTimestamp)

        log.debug("*** BEGIN Running parsers: %d (%s)" % (newForecast.timestamp, rmTimestampToDateAsString(newForecast.timestamp)))
        for parserConfig in self.parsers:
            if parserId is not None and parserId != parserConfig.dbID:
                continue

            log.debug("   * Parser: %s -> %s" % (parserConfig, parserConfig.runtimeLastForecastInfo))
            if parserConfig.enabled:
                if parserConfig.failCounter >= self.__maxFails:
                    if forceRunParser or parserConfig.lastFailTimestamp is None or (abs(newForecast.timestamp - parserConfig.lastFailTimestamp) >= self.__delayAfterMaxFails):
                        parserConfig.failCounter = 0
                        parserConfig.lastFailTimestamp = None
                    else:
                        if parserConfig.failCounter == self.__maxFails:
                            log.warning("     * Parser: %s - ignored because of lack of data (failCounter=%s, lastFail=%s)!" %
                                        (parserConfig, `parserConfig.failCounter`, rmTimestampToDateAsString(parserConfig.lastFailTimestamp)))
                            parserConfig.failCounter += 1 # Increment this to get rid of the above message.
                        continue
                elif parserConfig.failCounter > 0:
                    retryDelay = min(self.__minDelayBetweenFails + (parserConfig.failCounter - 1) * self.__stepDelayBetweenFails, self.__maxDelayBetweenFails)
                    nextRetryTimestamp = parserConfig.lastFailTimestamp + retryDelay
                    if newForecast.timestamp < nextRetryTimestamp:
                        log.debug("     * Ignored because retry delay %d (sec) was not reached" % retryDelay)
                        continue
                    log.debug("     * Parser retry after previous fail")

                parser = self.parsers[parserConfig]

                lastUpdate = None
                if parserConfig.runtimeLastForecastInfo:
                    # Check if parser hasn't run with an invalid future date
                    if parserConfig.runtimeLastForecastInfo.timestamp <= currentTimestamp:
                        lastUpdate = parserConfig.runtimeLastForecastInfo.timestamp

                # Save the newest parser run
                if lastUpdate is not None and lastUpdate > self.__lastUpdateTimestamp:
                    self.__lastUpdateTimestamp = lastUpdate

                if not forceRunParser and not self.forceParsersRun and (lastUpdate != None and (newForecast.timestamp - lastUpdate) < parser.parserInterval):
                    log.debug("     * Ignored because interval %d not expired for timestamp %d lastUpdate: %d" % (parser.parserInterval, newForecast.timestamp, lastUpdate))
                    continue

                log.debug("  * Running parser %s with interval %d" % (parser.parserName, parser.parserInterval))
                parser.settings = globalSettings.getSettings()
                parser.runtime[RMParser.RuntimeDayTimestamp] = rmCurrentDayTimestamp()

                try:
                    parser.lastKnownError = ''
                    parser.isRunning = True
                    parser.perform()
                    parser.isRunning = False
                except Exception, e:
                    log.error("  * Cannot execute parser %s" % parser.parserName)
                    log.exception(e)
                    parser.isRunning = False
                    if len(parser.lastKnownError) == 0:
                        parser.lastKnownError = 'Error: Failed to run'

                if not parser.hasValues():
                    parserConfig.failCounter += 1
                    parserConfig.lastFailTimestamp = newForecast.timestamp
                    if len(parser.lastKnownError) == 0:
                        parser.lastKnownError = 'Error: parser returned no values'
                    parser.isRunning = False
                    if parserConfig.failCounter == 1:
                        log.warn ("  * Parser %s returned no values" % parser.parserName)
                    continue


                parserConfig.failCounter = 0
                parserConfig.lastFailTimestamp = None

                if newForecast.id == None:
                    self.forecastTable.addRecordEx(newForecast)
                parserConfig.runtimeLastForecastInfo = newForecast

                if not globalSettings.vibration:
                    self.parserDataTable.removeEntriesWithParserIdAndTimestamp(parserConfig.dbID, parser.getValues())

                self.parserDataTable.addRecords(newForecast.id, parserConfig.dbID, parser.getValues())
                parser.clearValues()

                newValuesAvailable = True

        mixerDataValues = None
        if newValuesAvailable:
            globalDbManager.parserDatabase.vacuum()

            if not mixerDataValues is None:
                for parserConfig in self.parsers:
                    if parserConfig.runtimeLastForecastInfo:
                        parserConfig.runtimeLastForecastInfo.processed = True
        else:
            log.debug("  * No new value available from parsers")

        log.debug("*** END Running parsers: %s, %d (%s)" % (`newForecast.id`, newForecast.timestamp, rmTimestampToDateAsString(newForecast.timestamp)))
        return newForecast, mixerDataValues


    def __load(self, parserDir):
        log.info("*** BEGIN Loading parsers from '%s'" % parserDir)
        fileMap = OrderedDict()

        #---------------------------------------------------------------------------
        #
        #
        for root, dirs, files in os.walk(parserDir):
            for fname in files:
                tmpsplit = os.path.splitext(fname)
                modname = tmpsplit[0]
                modext = tmpsplit[1]
                modPath = os.path.join(root, fname)

                fileEntry = fileMap.get(modname, None)
                if fileEntry is None:
                    fileMap[modname] = {
                        "file": fname,
                        "name": modname,
                        "ext": modext,
                        "path": modPath
                    }
                else:
                    if modext == ".py":
                        fileEntry["file"] = fname
                        fileEntry["name"] = modname
                        fileEntry["ext"] = modext
                        fileEntry["path"] = modPath

        #---------------------------------------------------------------------------
        #
        #
        for fileEntry in fileMap.values():
            try:
                if fileEntry["ext"] == ".pyc" :
                    module = imp.load_compiled(fileEntry["name"], fileEntry["path"])
                elif fileEntry["ext"] == ".py" :
                    module = imp.load_source(fileEntry["name"], fileEntry["path"])
                else:
                    continue
            except Exception as e:
                log.error("  * Error loading parser %s from file '%s'" % (fileEntry["name"], fileEntry["path"]))
                log.exception(e)
                continue
            try:
                log.debug("  * Parser %s successful loaded from file '%s'" % (fileEntry["name"], fileEntry["path"]))
                parser = RMParser.parsers[-1] # Last added parser
                enabled = parser.isEnabledForLocation(globalSettings.location.timezone, \
                                                      globalSettings.location.latitude, \
                                                      globalSettings.location.longitude
                                                      )

                parserConfig, isNew = self.parserTable.addParser(fileEntry["file"], parser.parserName, enabled, parser.params)
                parser.defaultParams = parser.params.copy() # save the default parser params for an eventual params reset

                if not isNew:
                    params = self.parserTable.getParserParams(parserConfig.dbID)
                    unusedKeyList = []
                    if params:
                        for key in params:
                            bFound = False
                            for pkey in parser.params:
                                if key == pkey:
                                    bFound = True
                            if not bFound:
                                unusedKeyList.append(key)

                        for key in unusedKeyList:
                            params.pop(key, None)

                        parser.params.update(params)
                        self.parserTable.updateParserParams(parserConfig.dbID, parser.params)

                self.parsers[parserConfig] = parser

                parserConfig.userDataTypes = self.userDataTypeTable.addRecords(parser.userDataTypes)
                self.parserUserDataTypeTable.addRecords(parserConfig.dbID, parserConfig.userDataTypes)

                log.debug(parserConfig)
            except Exception, e:
                log.info("Failed to register parser from file : %s. Error: %s" % (fileEntry["name"], e))
                RMParser.parsers.pop()

        log.info("*** END Loading parsers")

    def findParserConfig(self, parserID):
        for parserConfig in self.parsers:
            if parserConfig.dbID == parserID:
                return parserConfig
        return None

    def setParserParams(self, parserID, params):
        parserConfig = self.findParserConfig(parserID)
        if parserConfig is None:
            return False

        parser = self.parsers[parserConfig]

        newParams = copy.deepcopy(parser.params)
        hasChanges = False

        try:
            for key, oldValue in parser.params.iteritems():
                newValue = params.get(key, None)
                if newValue is not None:
                    if oldValue is None or type(oldValue) == type(newValue):
                        newParams[key] = newValue
                        hasChanges = True
                    else:
                        log.warning("Types do not match: oldType=%s, newType=%s" % (type(oldValue), type(newValue)))
        except Exception, e:
            log.exception(e)
            return False

        if hasChanges:
            parser.params = newParams
            self.parserTable.updateParserParams(parserConfig.dbID, parser.params)
            self.parserDataTable.deleteRecordsByParser(parserConfig.dbID)

        return True

    # Will set the default parser parameters for a parser id
    def resetParserParams(self, parserID):

        parserConfig = self.findParserConfig(parserID)
        if parserConfig is None:
            return False

        parser = self.parsers[parserConfig]
        parser.params = parser.defaultParams
        self.parserTable.updateParserParams(parserConfig.dbID, parser.params)
        self.parserDataTable.deleteRecordsByParser(parserConfig.dbID)

        return True



    def activateParser(self, parserID, activate):
        parserConfig = self.findParserConfig(parserID)
        if parserConfig is None:
            return False

        parserConfig.enabled = (activate == True)
        self.parserTable.enableParser(parserConfig.dbID, parserConfig.enabled)

        return True

    def installParser(self, tempFilePath, fileName):
        filePath = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "parsers", fileName))
        shutil.move(tempFilePath, filePath)

        try:
            module = imp.load_source(fileName, filePath)

            log.info("  * Parser %s successful loaded from file '%s'" % (fileName, filePath))
            parser = RMParser.parsers[-1] # Last added parser
            enabled = parser.isEnabledForLocation(globalSettings.location.timezone, \
                                                  globalSettings.location.latitude, \
                                                  globalSettings.location.longitude
                                                  )

            parserConfig, isNew = self.parserTable.addParser(fileName, parser.parserName, enabled, parser.params)
            if not isNew:
                params = self.parserTable.getParserParams(parserConfig.dbID)
                if params:
                    parser.params = params
                RMParser.parsers.pop()
                #delete old entry
                pkeys = self.parsers.keys()
                for pkey in pkeys:
                    if parserConfig.dbID is pkey.dbID:
                        del self.parsers[pkey]

            self.parsers[parserConfig] = parser

            parserConfig.userDataTypes = self.userDataTypeTable.addRecords(parser.userDataTypes)
            self.parserUserDataTypeTable.addRecords(parserConfig.dbID, parserConfig.userDataTypes)

            log.debug(parserConfig)

            return True

        except Exception as e:
            try:
                if os.path.exists(filePath):
                    os.remove(filePath)
            except Exception, e:
                log.exception(e)

            log.error("  * Error installing/loading parser %s from file '%s'" % (fileName, filePath))
            log.exception(e)

        return False

    def resetToDefault(self):
        log.info("**** BEGIN Reset parsers and mixer to default")

        result = False
        try:
            self.mixer.resetToDefault()

            self.parserDataTable.clear(False)
            self.forecastTable.clear(False)
            globalDbManager.parserDatabase.commit()

            for parserConfig in self.parsers:
                parserConfig.runtimeLastForecastInfo = None
                parserConfig.failCounter = 0
                parserConfig.lastFailTimestamp = None

                parser = self.parsers[parserConfig]
                enabled = parser.isEnabledForLocation(globalSettings.location.timezone,
                                                      globalSettings.location.latitude,
                                                      globalSettings.location.longitude
                                                      )

                self.parserTable.addParser(parserConfig.fileName, parserConfig.name, enabled, parser.params)

            result = True
        except Exception, e:
            log.exception(e)

        log.info("**** END Reset parsers and mixer to default")

        return result
