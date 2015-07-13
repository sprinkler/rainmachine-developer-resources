# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log

import datetime, time, random


class SimulatorParser(RMParser):
    parserName = "Simulator Parser"
    parserEnabled = False
    parserDebug = False
    parserInterval = 3 * 3600
    params = {}

    def __init__(self):
        RMParser.__init__(self)
        self.tempMin = -5.0
        self.tempMax = 2.0
        self.tempStep = (self.tempMax - self.tempMin) / 10.0

        self.qpfMin = 0.0
        self.qpfMax = 1.0
        self.qpfStep = (self.qpfMax - self.qpfMin) / 10.0

        self.dewMin = 0.0
        self.dewMax = 0.0
        self.dewStep = (self.dewMax - self.dewMin) / 10.0

        self.windMin = 0.0
        self.windMax = 2.0
        self.windStep = (self.windMax - self.windMin) / 10.0

        self.popMin = 1.0
        self.popMax = 2.0
        self.popStep = (self.popMax - self.popMin) / 10.0

        self.humidityMin = 40.0
        self.humidityMax = 60.0
        self.humidityStep = (self.humidityMax - self.humidityMin) / 10.0

    def isEnabledForLocation(self, timezone, lat, long):
        return SimulatorParser.parserEnabled

    def perform(self):

        startDayTimestamp = self._currentDayTimestamp()
        noOfDays = 7

        #-----------------------------------------------------------------------------------------------
        #
        # Get hourly data.
        #
        self.addValues(RMParser.dataType.TEMPERATURE, self._generateTemperature(startDayTimestamp, noOfDays))
        self.addValues(RMParser.dataType.QPF, self._generateQpf(startDayTimestamp, noOfDays))
        self.addValues(RMParser.dataType.DEWPOINT, self._generateDewPoint(startDayTimestamp, noOfDays))
        self.addValues(RMParser.dataType.WIND, self._generateWind(startDayTimestamp, noOfDays))
        self.addValues(RMParser.dataType.POP, self._generatePop(startDayTimestamp, noOfDays))
        self.addValues(RMParser.dataType.RH, self._generateHumidity(startDayTimestamp, noOfDays))

        #-----------------------------------------------------------------------------------------------
        #
        # Get daily data.
        #
        #self.addValues(RMParser.dataType.CONDITION, parsedConditions)

        if self.parserDebug:
            log.debug(self.result)


    def _generateTemperature(self, startDayTimestamp, noOfDays):
        values = [(hourTimestamp, self._randRange(self.tempMin, self.tempMax, self.tempStep))
                  for hourTimestamp in range(startDayTimestamp, startDayTimestamp + noOfDays * 24 * 3600, 3600)
                ]
        return values

    def _generateQpf(self, startDayTimestamp, noOfDays):
        values = [(hourTimestamp, self._randRange(self.qpfMin, self.qpfMax, self.qpfStep))
                  for hourTimestamp in range(startDayTimestamp, startDayTimestamp + noOfDays * 24 * 3600, 3600)
                ]
        return values

    def _generateDewPoint(self, startDayTimestamp, noOfDays):
        values = [(hourTimestamp, self._randRange(self.dewMin, self.dewMax, self.dewStep))
                  for hourTimestamp in range(startDayTimestamp, startDayTimestamp + noOfDays * 24 * 3600, 3600)
                ]
        return values

    def _generateWind(self, startDayTimestamp, noOfDays):
        values = [(hourTimestamp, self._randRange(self.windMin, self.windMax, self.dewStep))
                  for hourTimestamp in range(startDayTimestamp, startDayTimestamp + noOfDays * 24 * 3600, 3600)
                ]
        return values

    def _generatePop(self, startDayTimestamp, noOfDays):
        values = [(hourTimestamp, self._randRange(self.popMin, self.popMax, self.popStep))
                  for hourTimestamp in range(startDayTimestamp, startDayTimestamp + noOfDays * 24 * 3600, 3600)
                ]
        return values

    def _generateHumidity(self, startDayTimestamp, noOfDays):
        values = [(hourTimestamp, self._randRange(self.humidityMin, self.humidityMax, self.humidityStep))
                  for hourTimestamp in range(startDayTimestamp, startDayTimestamp + noOfDays * 24 * 3600, 3600)
                ]
        return values

    def _randRange(self, min, max, step):
        factor = 100.0
        min = int(min * factor)
        max = int(max * factor)
        step = int(step * factor)

        try:
            if min == max:
                return min / factor
            if step == 0:
                return random.randrange(min, max) / factor
            return random.randrange(min, max, step) / factor
        except Exception, e:
            log.error(e)

        return min / factor

    def _currentDayTimestamp(self):
        return self._getStartOfDay(int(time.time()))

    def _getStartOfDay(self, timestamp):
        tuple = datetime.datetime.fromtimestamp(timestamp).timetuple()
        return int(datetime.datetime(tuple.tm_year, tuple.tm_mon, tuple.tm_mday).strftime("%s"))