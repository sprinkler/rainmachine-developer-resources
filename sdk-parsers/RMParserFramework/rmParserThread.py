# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from threading import Thread
from Queue import Queue, Empty

from RMDatabaseFramework.rmDatabase import *
from RMDatabaseFramework.rmMixerDataTable import *
from RMDataFramework.rmUserSettings import *
from RMDatabaseFramework.rmDatabaseManager import globalDbManager
from RMParserFramework.rmParserManager import RMParserManager
from RMUtilsFramework.rmLogging import log

class RMParserThread(Thread):
    def __init__(self):
        Thread.__init__(self)

        self.__simulator = None
        self.__parserManager = None
        self.__mixerDataTable = None

        self.__useThreading = False
        if self.__useThreading:
            self.__stop = False
            self.__waitTimeout = 3600
            self.__messageQueue = Queue()

    #----------------------------------------------------------------------------------------
    #
    #
    #
    @property
    def simulator(self):
        return self.__simulator

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def start(self):
        if self.__useThreading:
            Thread.start(self)
        else:
            self.__preRun()

    def join(self, timeout=None):
        if self.__useThreading:
            Thread.join(self, timeout)

    def run(self):
        if not self.__useThreading:
            self.__run()
            return

        #-----------------------------------------------------------
        #
        log.info("Parser Thread is running!")
        self.__preRun()

        while not self.__stop:
            #-------------------------------------------------------------------------
            # Run parsers, mixer and simulator.
            self.__run()

            #-------------------------------------------------------------------------
            # Handle the events we might have received.
            message = None
            while True:
                try:
                    message = self.__messageQueue.get(True, self.__waitTimeout)
                    if message == "shutdown":
                        break
                    elif message == "settingschanged-location":
                        if self.__parserManager.resetToDefault():
                            self.__run(None, True)
                        break
                except Empty, e:
                    break

            if message == "shutdown":
                break

        #-----------------------------------------------------------
        #
        self.__postRun()

        log.info("ParserThread shutdown complete!")

    def stop(self):
        if self.__useThreading:
            log.info("Parser Thread is going to shutdown now...")
            self.__stop = True
            self.__messageQueue.put("shutdown")
        else:
            self.__postRun()

    def resetToDefault(self):
        if self.__useThreading:
            self.__messageQueue.put_nowait("settingschanged-location")
        elif self.__parserManager.resetToDefault():
            self.__run(None, True)

    def resetMixerSimulator(self):
        try:
            forecast, mixerDataValues = self.__parserManager.resetMixerToDefault()
        except Exception, e:
            log.error("Exception encountered while resetting the Mixer/Simulator!")
            log.exception(e)

    def runParser(self, parserId, runParser, runMixer, runSimulator):
        self.__run(parserId, runParser, runMixer, runSimulator)

    def simulateProgram(self, programId):
        self.__simulator.simulateProgram(programId)

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def __preRun(self):
        #-----------------------------------------------------------
        #
        self.__parserManager = RMParserManager()
        self.__mixerDataTable = RMMixerDataTable(globalDbManager.mixerDatabase)

        if globalSettings.wizardHasRun:
            try:
                forecast, mixerDataValues = self.__parserManager.preRun()
                if forecast:
                    self.__simulate(forecast.id, forecast.timestamp, mixerDataValues)
            except Exception, e:
                log.error("Exception encountered while pre-running the Simulator!")
                log.exception(e)

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def __run(self, parserId = None, forceRunParser = False, forceRunMixer = False, forceRunSimulator = False):
        if not globalSettings.wizardHasRun:
            return

        forecast, mixerDataValues = None, None

        try:
            forecast, mixerDataValues = self.__parserManager.run(parserId, forceRunParser, forceRunMixer)
        except Exception, e:
            log.error("Exception encountered while running the Parser Manager!")
            log.exception(e)

        if forceRunSimulator:
            if forecast is None and mixerDataValues is None:
                pass

            mixerData = self.__mixerDataTable.getRecordsByForecast(True)
            if mixerData:
                for forecastID in mixerData:
                    forecastData = mixerData[forecastID]
                    forecastTimestamp = forecastData["timestamp"]
                    mixerDataValues = forecastData["values"]

                    self.__simulate(forecastID, forecastTimestamp, mixerDataValues)
        elif forecast:
            self.__simulate(forecast.id, forecast.timestamp, mixerDataValues)

    def __simulate(self, forecastID, forecastTimestamp, mixerDataValues):
        if mixerDataValues is not None:
            for mixerData in mixerDataValues:
                globalSettings.restrictions.setDayMinTemperature(mixerData.timestamp, mixerData.minTemp)


    #----------------------------------------------------------------------------------------
    #
    #
    #
    def __postRun(self):

        self.__simulator = None
        self.__parserManager = None
        log.info("ParserThread postRun() complete!")
