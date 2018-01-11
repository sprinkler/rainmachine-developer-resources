# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import sys
import os
import copy

from RMUtilsFramework import rmTimeUtils
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
import RMUtilsFramework.rmUtils as rmUtils
from RMDatabaseFramework.rmUserSettingsTable import RMUserSettingsTable
from RMCore.version import __version__

class RMUserSettingsLocation:
    def __init__(self):
        self.zip = None
        self.name = "Default"
        self.state = "Default"
        self.latitude = None
        self.longitude = None
        self.address = "Default"
        self.elevation = 10.0
        self.timezone = "America/Los_Angeles"
        self.stationID = None
        self.stationName = "Default"
        self.stationSource = ""
        self.et0Average = 5.0
        self.rainSensitivity = 0.8
        self.windSensitivity = 0.5
        self.krs = 0.19
        self.wsDays = 2

        self.stationDownloaded = False
        self.doyDownloaded = False

    def asDict(self):
        return dict((key, value) for key, value in self.__dict__.iteritems() if not callable(value) and not key.startswith('_'))

    def __repr__(self):
        v = vars(self)
        return ",".join([":".join((k, str(v[k]))) for k in v if not k.startswith("_")])

class RMUserSettings:
    __metaclass__ = rmUtils.RMSingleton

    def __init__(self):

        self.wizardHasRun = False
        self.standaloneMode = False

        self.useCommandLineArguments = False
        self.useDemoData = False
        self.firstRun = False

        self.auth = {}

        self.netName = "RainMachine"
        self.locationUnits = "C"

        self.useCorrectionForPast = False
        self.programSingleSchedule = False
        self.runParsersBeforePrograms = True # If we should try to run weather parsers before program start time
        self.minWateringDurationThreshold = 0 # 0 seconds
        self.useMasterValve = False
        self.maxWateringCoef = 2.0
        self.masterValveBefore = 0
        self.masterValveAfter = 0
        self.localValveCount = 8
        self.defaultZoneWateringDuration = 5 * 60 # for how many seconds to run a zon by default, when started from local touchscreen
        self.zoneDuration = self.localValveCount * [ self.defaultZoneWateringDuration ]      # for how many seconds to run a each zone when started from local touchscreen

        self.httpEnabled = True
        self.zoneListShowInactive = True
        self.programListShowInactive = True
        self.programZonesShowInactive = False
        self.selfTest = False

        self.maxLEDBrightness = 40
        self.minLEDBrightness = 0
        self.showRestrictionsOnLed = False # If restrictions should light the DELAY led. Otherwise only when it's rain delay the led will be on
        self.touchAdvanced = False # Allow advanced usage of touchscreen for queueing multiple zones
        self.touchAuthAPSeconds = 60 # How many seconds to allow restricted API calls in open AP mode after button press
        self.touchSleepTimeout = 10 # After how many seconds after user interaction the display will sleep
        self.touchLongPressTimeout = 3 # How many seconds longPress should automatically register as an up event
        self.touchCyclePrograms = True
        self.touchProgramToRun = None

        self.location = RMUserSettingsLocation()
        self.cloud = {}

        self.useRainSensor = False # If we should use the hardware rainsensor in restricting watering
        self.rainSensorIsNormallyClosed = True # If rain sensors opens the circuit when rain is detected
        self.useSoftwareRainSensor = False  # If we should use a software rainsensor
        self.softwareRainSensorMinQPF = 5.0  # The minimum QPF for a day for which we restrict

        self.restrictions = {}

        self.__settingsTable = None
        self.__hourlyRestrictionsTable = None
        self.__defaultSettings = None

        self.databasePath = None
        self.parserDataSizeInDays = 6
        self.parserHistorySize = 365
        self.mixerHistorySize = 365
        self.simulatorHistorySize = 0
        self.waterLogHistorySize = 365

        self.doyDownloadUrl = "http://graphs.rainmachine.com"

        self.httpsServerPort = 8080
        self.httpServerPort = 18080

        self.apiVersion = "4.2.0"
        self.hardwareVersion = "2.0"
        self.softwareVersion = __version__

        self.vibration = False

        self.allowAlexaDiscovery = False

    def dumpInfo(self):
        log.info("---------------------------------------------------------------------------------------------")
        log.info("Version (%(ver)s) Running for:\n- name: %(name)s\n- timezone: %(tz)s\n- latitude: %(lat)s\n- longitude: %(lon)s\n"
                 "- elevation: %(elev)s\n"
                 "- et0Average: %(et0avg)s\n- krs: %(krs)s\n- rainSensitivity: %(rs)s\n"
                 "- windSensitivity: %(ws)s\n- wsDays: %(wsdays)s\n"
                 "- database path: %(db)s\n"
                 "- httpsServerPort: %(https)s (ssl)\n- httpServerPort: %(http)s\n"
                 "- wizardHasRun: %(wizard)d" % {
                'ver': `self.softwareVersion`,
                'name': `self.location.name`,
                'tz': `self.location.timezone`,
                'lat': `self.location.latitude`,
                'lon': `self.location.longitude`,
                'elev': `self.location.elevation`,
                'et0avg': `self.location.et0Average`,
                'rs': `self.location.rainSensitivity`,
                'ws': `self.location.windSensitivity`,
                'krs': `self.location.krs`,
                'wsdays': `self.location.wsDays`,
                'db': `self.databasePath`,
                'https': `self.httpsServerPort`,
                'http': `self.httpServerPort`,
                'wizard': self.wizardHasRun})
        log.info("---------------------------------------------------------------------------------------------")

    def parseSysArguments(self, overrideDB):
        if len(sys.argv) >= 2:
            try:
                locationInfo = sys.argv[1].split(",")
                if len(locationInfo) >= 5:
                    locationName = locationInfo[0]
                    timezone = locationInfo[1]
                    locationLat = float(locationInfo[2])
                    locationLong = float(locationInfo[3])
                    elevation = float(locationInfo[4])

                    self.location.name = locationName
                    self.location.timezone = timezone
                    self.location.latitude = locationLat
                    self.location.longitude = locationLong
                    self.location.elevation = elevation

                if len(sys.argv) >= 3:
                    httpPorts = sys.argv[2].split(",")
                    httpsPort = self.httpsServerPort
                    httpPort = self.httpServerPort

                    if len(httpPorts) > 0:
                        httpsPort = int(httpPorts[0])
                        if len(httpPorts) > 1:
                            httpPort = int(httpPorts[1])
                        else:
                            httpPort = httpsPort

                    self.httpsServerPort = httpsPort
                    self.httpServerPort = httpPort

                self.useCommandLineArguments = True
                self.wizardHasRun = True

            except Exception, e:
                log.error("Exception encountered while parsing the input parameters!")
                log.error(e)
                exit(1)

        if overrideDB:
            mainDir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
            self.databasePath = os.path.join(mainDir, "DB", self.location.name)

    def getSettings(self):
        return copy.deepcopy(self)

    def setDatabase(self, settingsDatabase):
        self.__settingsTable = RMUserSettingsTable(settingsDatabase)

    def loadSettings(self):
        self.__settingsTable.loadAllRecords(self)
        self.__defaultSettings = copy.deepcopy(self)

    def saveSettings(self):
        self.__settingsTable.saveRecords(self.asDict(), self.location.asDict(),
                                         self.restrictions.globalRestrictions.asDict(),
                                         self.cloud.asDict())

    def updateSettings(self, system = None, location = None, restrictions = None):
        log.debug(system)
        log.debug(location)

        if system:
            self.updateExistingKeys(system)

        if location:
            if self.validateLocationSettings(location):
                self.location.__dict__.update(location)
                self.wizardHasRun = not self.location.timezone is None # Don't check location since sprinkler might be running in AP/no internet mode
                                    #and \
                                    #not self.location.latitude is None and \
                                    #not self.location.longitude is None and \
                                    #not self.location.elevation is None
                return True
            return False
        return True

    def validateLocationSettings(self, settings):
        try:
            name = settings.get("name")
            timezone = settings.get("timezone")
            latitude = settings.get("latitude")
            longitude = settings.get("longitude")
            elevation = settings.get("elevation")
            krs = settings.get("krs")

            if not timezone is None:
                if not timezone:
                    return False

            if not name is None:
                if not name:
                    return False

            if not latitude is None:
                settings["latitude"] = float(latitude)

            if not longitude is None:
                settings["longitude"] = float(longitude)

            if not elevation is None:
                settings["elevation"] = float(elevation)
            else:
                log.warning("Elevation not set!")

            if not krs is None:
                settings["krs"] = float(krs)
            else:
                log.warning("Krs not set")

            return True
        except Exception, e:
            log.error(e)
        return False

    def restoreDefaultSettings(self):
        self.__settingsTable.deleteAll()
        self.__settingsTable.saveRecords(self.__defaultSettings.asDict(), self.__defaultSettings.location.asDict(),
                                         self.__defaultSettings.restrictions.globalRestrictions.asDict(),
                                         self.__defaultSettings.cloud.asDict())
    def asDict(self):
        return dict((key, value) for key, value in self.__dict__.iteritems() if not callable(value) and not key.startswith('_')
                                        and not key.startswith('auth')
                                        and not key.startswith('useDemoData')
                                        and not key.startswith('location')
                                        and not key.startswith('restrictions')
                                        and not key.startswith('doyDownloadUrl')
                                        and not key.startswith('httpsServerPort')
                                        and not key.startswith('httpServerPort')
                                        and not key.startswith('softwareVersion')
                                        and not key.startswith('apiVersion')
                                        and not key.startswith('cloud')
                                        and not key.startswith('firstRun'))

    def updateExistingKeys(self, dict):
        for key, value in dict.iteritems():
            if key in self.__dict__.keys() and not callable(self.__dict__[key]) and not key.startswith('_'):
                self.__dict__[key] = value


globalSettings = RMUserSettings()
