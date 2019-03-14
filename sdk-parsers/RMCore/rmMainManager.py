# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import os, shutil, time, stat
import Queue

from RMDataFramework.rmUserSettings import globalSettings
from RMDatabaseFramework.rmDatabase import RMMainDatabase
from RMDatabaseFramework.rmDatabase import RMUserSettingsDatabase
from RMDatabaseFramework.rmDatabaseManager import globalDbManager
from RMParserFramework.rmParserThread import RMParserThread
from RMUtilsFramework.rmUtils import RMSingleton
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmThreadWatcher import RMThreadWatcher
from RMUtilsFramework.rmCommandThread import RMCommand

class RMMainManager:
    __metaclass__ = RMSingleton

    #-------------------------------------------------------------------------------------------------------
    #
    #
    instance = None

    @staticmethod
    def createInstance():
        if RMMainManager.instance is None:
            RMMainManager.instance = RMMainManager()
            return RMMainManager.instance.setup()
        return False

    #-------------------------------------------------------------------------------------------------------
    #
    #
    def __init__(self):
        self.__httpServerThread = None
        self.__parserThread = None
        self.__localNetworkAdvertiser = None

        self.__programScheduler = None

        self.__stopRunning = False
        self.__resetToDefault = False
        self.__factoryReset = False
        self.__sysUpgrade = False
        self.__shutdown = False
        self.__reboot = False
        self.__restart = False
        self.__wifiChanged = False

        self.__sysUpgradeFilePath = None

        self.__messageQueue = Queue.Queue()
        self.__alexaServer = None

    def setup(self):
        if not os.path.exists(globalSettings.databasePath):
            try:
                os.makedirs(globalSettings.databasePath)
            except Exception, e:
                log.error("Exception encountered while creating the database directory: %s" % (globalSettings.databasePath))
                log.error(e)
                return False

        globalSettings.setDatabase(globalDbManager.settingsDatabase)
        globalSettings.loadSettings()

        globalSettings.parseSysArguments(False) # Force usage of command line arguments, if they are present.

        return True

    def run(self):
        self.__stopRunning = False

        self.__preRun()

        RMThreadWatcher.createInstance()
        RMThreadWatcher.instance.registerThread("Main Manager", 60 * 7)
        RMThreadWatcher.instance.setMainManager(self)

        self.__parserThread = RMParserThread()
        self.__parserThread.start()


        while not self.__stopRunning:
            RMThreadWatcher.instance.updateThread()
            
            if globalSettings.wizardHasRun:
                self.__parserThread.run()

            messageLoopTimestamp = int(time.time())

            while True:
                waitTime = 60 + messageLoopTimestamp - int(time.time())

                if waitTime <= 0:
                    break

                try:
                    command = self.__messageQueue.get(True, waitTime)
                    log.debug(command.name)

                    if command.name == "savesettings":
                        globalSettings.saveSettings()
                        globalSettings.loadSettings()
                        break
                    elif command.name == "settingschanged-location":
                        self.__programScheduler.resetToDefault()
                        self.__parserThread.resetToDefault()
                        break
                    elif command.name == "settingschanged-geolocation":
                        self.__programScheduler.resetToDefault()
                        self.__clearStationAndDoy()
                        self.__updateStation()
                        self.__updateDoyDatabase()
                        self.__parserThread.resetToDefault()
                        break
                    elif command.name == "reset-mixer-simulator":
                        self.__parserThread.resetMixerSimulator()
                        break
                    elif command.name == "run-parser":
                        self.__parserThread.runParser(command.parserId, command.runParser, command.runMixer, command.runSimulator)
                        break
                    elif command.name == "simulate-program":
                        self.__parserThread.simulateProgram(command.programId)
                        break
                    elif command.name == "systemDateTimeChanged":
                        self.__systemDateTimeChanged()
                        break
                    elif command.name == "resetToDefault":
                        self.__resetToDefault = True
                        if command.shouldRestart:
                            self.__restart = True
                        self.__stopRunning = True
                        break
                    elif command.name == "resetToDefaultAndRestart":
                        self.__resetToDefault = True
                        self.__restart = True
                        self.__stopRunning = True
                        break
                    elif command.name == "factoryReset":
                        self.__factoryReset = True
                        self.__reboot = True
                        self.__stopRunning = True
                        break
                    elif command.name == "stop":
                        self.__stopRunning = True
                        break
                    elif command.name == "shutdown":
                        self.__stopRunning = True
                        self.__shutdown = True
                        break
                    elif command.name == "reboot":
                        self.__stopRunning = True
                        self.__reboot = True
                        break
                    elif command.name == "restart":
                        self.__stopRunning = True
                        self.__restart = True
                        break
                except Queue.Empty, e:
                    break

        RMThreadWatcher.instance.stop()
        RMThreadWatcher.instance.join()

        self.__parserThread.stop()
        self.__parserThread.join()

        self.__postRun()

    def stop(self, shutdown = False):
        if shutdown:
            self.__messageQueue.put_nowait(RMCommand("shutdown", False))
        else:
            self.__messageQueue.put_nowait(RMCommand("stop", False))

    def reboot(self):
        self.__messageQueue.put_nowait(RMCommand("reboot", False))

    def restart(self):
        self.__messageQueue.put_nowait(RMCommand("restart", False))

    #-------------------------------------------------------------------------------------------------------
    #
    #
    def updateSettings(self, system = None, location = None, restrictions = None):
        oldLat = globalSettings.location.latitude
        oldLong = globalSettings.location.longitude
        oldElevation = globalSettings.location.elevation
        oldStationId = globalSettings.location.stationID


        oldZip = globalSettings.location.zip
        oldState = globalSettings.location.state
        oldAddress = globalSettings.location.address
        oldTimezone = globalSettings.location.timezone

        oldRainSensitivity = int(globalSettings.location.rainSensitivity * 1000)
        oldWindSensitivity = int(globalSettings.location.windSensitivity * 1000)
        oldWsDays = int(globalSettings.location.wsDays * 1000)

        if globalSettings.updateSettings(system=system, location=location):
            #---------------------------------------------------------------
            #
            if location and location.get("timezone") and globalSettings.location.timezone:
                globalSystemDateTime.setTimeZone(globalSettings.location.timezone)


            #---------------------------------------------------------------
            #
            self.__messageQueue.put_nowait(RMCommand("savesettings", False))
            if location:
                geoLocationChanged = (oldLat != globalSettings.location.latitude) or \
                                     (oldLong != globalSettings.location.longitude) or \
                                     (oldElevation != globalSettings.location.elevation) or \
                                     (oldStationId != globalSettings.location.stationID)

                locationChanged = (oldZip != globalSettings.location.zip) or \
                                  (oldState != globalSettings.location.state) or \
                                  (oldAddress != globalSettings.location.address) or \
                                  (oldTimezone != globalSettings.location.timezone)

                resetMixerSimulator = (oldRainSensitivity != int(globalSettings.location.rainSensitivity * 1000)) or \
                                 (oldWsDays != int(globalSettings.location.wsDays * 1000)) or \
                                 (oldWindSensitivity != int(globalSettings.location.windSensitivity * 1000))

                if geoLocationChanged:
                    self.__messageQueue.put_nowait(RMCommand("settingschanged-geolocation", False))
                elif locationChanged:
                    self.__messageQueue.put_nowait(RMCommand("settingschanged-location", False))
                elif resetMixerSimulator:
                    self.__messageQueue.put_nowait(RMCommand("reset-mixer-simulator", False))
            return True
        return False

    #-------------------------------------------------------------------------------------------------------
    #
    #
    def resetToDefault(self, shouldRestart):
        command = RMCommand("resetToDefault", False)
        command.shouldRestart = shouldRestart
        self.__messageQueue.put_nowait(command)

    #-------------------------------------------------------------------------------------------------------
    #
    #
    def factoryReset(self):
        self.__messageQueue.put_nowait(RMCommand("factoryReset", False))

    def systemDateTimeChanged(self):
        self.__messageQueue.put_nowait(RMCommand("systemDateTimeChanged", False))

    def __systemDateTimeChanged(self):
        log.warning("System time has changed! Stopping all programs!")
        self.__programScheduler.stopAllPrograms()

    #-------------------------------------------------------------------------------------------------------
    #
    #
    def cloudClientSettingsChanged(self, string):
        command = RMCommand("notifyCloud", False)
        command.string = string
        self.__messageQueue.put_nowait(command)

    def __notifyCloudClientSettingsChange(self):
        RMNotification.notifyCloud(RMNotification.cloudClient, None, None)

    #-------------------------------------------------------------------------------------------------------
    #
    #
    def runParser(self, parserId, runParser, runMixer, runSimulator):
        command = RMCommand("run-parser", False)
        command.parserId = parserId
        command.runParser = runParser
        command.runMixer = runMixer
        command.runSimulator = runSimulator
        self.__messageQueue.put_nowait(command)
        return True


    #-------------------------------------------------------------------------------------------------------
    #
    #
    def __preRun(self):

        if globalSettings.firstRun :
            log.info("*** No existing databases found assuming first run")

            globalSettings.saveSettings()
            globalSettings.loadSettings()

    def __postRun(self):
        pass

    #-------------------------------------------------------------------------------------------------------
    #
    #
    @property
    def shouldResetToDefault(self):
        return self.__resetToDefault

    @property
    def shouldFactoryReset(self):
        return self.__factoryReset

    @property
    def shouldSysUpgrade(self):
        return self.__sysUpgrade

    @property
    def shouldShutdown(self):
        return self.__shutdown

    @property
    def shouldReboot(self):
        return self.__reboot

    @property
    def shouldRestart(self):
        return self.__restart

    @property
    def sysUpgradeFilePath(self):
        return self.__sysUpgradeFilePath
