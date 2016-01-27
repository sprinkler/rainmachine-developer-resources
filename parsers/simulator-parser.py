# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMParserFramework.rmParserManager import RMParserManager
from RMUtilsFramework.rmTimeUtils import rmGetStartOfDayUtc

import datetime, time, random, math


class SimulatorParser(RMParser):
    parserName = "Simulator Parser"
    parserEnabled = False
    parserDebug = False
    parserInterval = 3 * 3600
    params = {
        "minTemp" : 5,
        "maxTemp" : 25,
        "_lastTS": [],
        "_rain6qpf": []
    }

    def __init__(self):
        RMParser.__init__(self)
        self.tempMin = -5.0
        self.tempMax = 20.0
        self.tempStep = (self.tempMax - self.tempMin) / 10.0

        self.qpfMin = 0.0
        self.qpfMax = 1.0
        self.qpfStep = (self.qpfMax - self.qpfMin) / 10.0

        self.dewMin = 0.0
        self.dewMax = 10.0
        self.dewStep = (self.dewMax - self.dewMin) / 10.0

        self.windMin = 0.0
        self.windMax = 2.0
        self.windStep = (self.windMax - self.windMin) / 10.0

        self.popMin = 0.0
        self.popMax = 12.0
        self.popStep = (self.popMax - self.popMin) / 10.0

        self.humidityMin = 40.0
        self.humidityMax = 60.0
        self.humidityStep = (self.humidityMax - self.humidityMin) / 10.0

    def isEnabledForLocation(self, timezone, lat, long):
        return SimulatorParser.parserEnabled

    def perform(self):
        if self.params["minTemp"] is not None:
            self.tempMin = self.params["minTemp"]
        if self.params["maxTemp"] is not  None:
            self.tempMax = self.params["maxTemp"]

        startDayTimestamp = (self._currentDayTimestamp())
        #prediction timestamps
        noOfDays = 6
        arrTimestamps = [x for x in range(startDayTimestamp, startDayTimestamp+noOfDays*24*3600, 4*3600)]

        #-----------------------------------------------------------------------------------------------
        #
        # Get hourly data.
        self.addValues(RMParser.dataType.TEMPERATURE, self._generatePeriodicalData(arrTimestamps, self.tempMin
            , self.tempMax, 6, -2.5))

        self.addValues(RMParser.dataType.MINTEMP, self._generateCumulativeData(arrTimestamps, self.tempMin/2, self.tempMin*2))
        self.addValues(RMParser.dataType.MAXTEMP, self._generateCumulativeData(arrTimestamps, self.tempMax/2, self.tempMax*2))

        self.addValues(RMParser.dataType.DEWPOINT, self._generateCumulativeData(arrTimestamps, self.dewMin, self.dewMax))
        self.addValues(RMParser.dataType.WIND, self._generateCumulativeData(arrTimestamps, self.windMin, self.windMax))
        self.addValues(RMParser.dataType.POP, self._generateCumulativeData(arrTimestamps, self.popMin, self.popMax))
        self.addValues(RMParser.dataType.RH, self._generatePeriodicalData(arrTimestamps, 2*math.fabs(self.tempMin)
            , 2*math.fabs(self.tempMax), 6, 0))

        #-----------------------------------------------------------------------------------------------
        #
        # Get daily data.
        #
        #self.addValues(RMParser.dataType.CONDITION, parsedConditions)
        #
        self._generateQpfRainModelData()
        #
        ##add history for yesterday
        startYesterday = self._currentDayTimestamp() - 24*3600
        self.addValue(RMParser.dataType.TEMPERATURE, startYesterday, (self.tempMax+self.tempMin)*random.random())
        self.addValue(RMParser.dataType.MINTEMP, startYesterday, self.tempMin*random.random())
        self.addValue(RMParser.dataType.MAXTEMP, startYesterday, self.tempMax*random.random())
        self.addValue(RMParser.dataType.RH, startYesterday, (self.humidityMin+self.humidityMax)*random.random())
        self.addValue(RMParser.dataType.MINRH, startDayTimestamp, self.humidityMin*random.random())
        self.addValue(RMParser.dataType.MAXRH, startDayTimestamp, self.humidityMax*random.random())

        if self.parserDebug:
            log.debug(self.result)

    def _generateQpfRainModelData(self):
        noOfDays = 7
        startDayTimestamp = self._currentDayTimestamp()

        oldTS = self.params["_lastTS"]
        rain6qpf = self.params["_rain6qpf"]
        lenqpf = len(rain6qpf)
        if len(oldTS) > 0 and startDayTimestamp in oldTS: #already first run and ran since last 6 days
            if oldTS[1] < startDayTimestamp  :  # a number of days have passed
                idxDay = oldTS.index(startDayTimestamp)
                rain6qpf[0:lenqpf-idxDay] = [(g + (random.random()-0.5)*idx) for idx, g in enumerate(rain6qpf[idxDay:])]
                rain6qpf[idxDay:] = [(random.random()-0.5) for g in rain6qpf[idxDay:]]
            else:# same day different hour
                rain6qpf[1:7] = [(g + (random.random()-0.5)*idx) for idx, g in enumerate(rain6qpf[1:7])]
        else:
            rain6qpf[0:7] = [(random.random()-0.5)*10 for g in range(0, 7)]

        for idx,val in enumerate(rain6qpf):
            if val <=0:
                rain6qpf[idx] = 0.1

        oldTS = [ts for ts in range(startDayTimestamp-24*3600, startDayTimestamp+(noOfDays-1)*24*3600, 24*3600)]

        self.params["_lastTS"] = oldTS
        self.params["_rain6qpf"] = rain6qpf

        for parserCfg in RMParserManager.instance.parsers:
            if self.parserName is parserCfg.name:
                RMParserManager.instance.setParserParams(parserCfg.dbID, self.params)
                break

        self.addValue(RMParser.dataType.RAIN, startDayTimestamp-24*3600, rain6qpf[0])
        qpf = zip(oldTS[1:], rain6qpf[1:])
        self.addValues(RMParser.dataType.QPF, qpf)


    def _generateCumulativeData(self, timestamps, minVal, maxVal):
        startVal = minVal + random.random()*(maxVal-minVal)
        result = []
        for idx, ts in enumerate(timestamps):
            if idx is 0:
                result.append(startVal)
            else:
                result.append(result[idx-1] + 0.2*(maxVal-minVal)*(random.random()-0.5))
            if result[idx] < minVal:
                result[idx] = minVal
            if result[idx] > maxVal:
                result[idx] = maxVal
        return zip(timestamps, result)

    def _generatePeriodicalData(self, timestamps, minVal, maxVal, step, offset):
        dOffset = offset/step * math.pi*2
        valArg = [minVal+ 0.5*(1+ 0.25*(random.random()-0.5))*(maxVal-minVal)*(math.sin(x + (1+ 0.5*(random.random()-0.5))*dOffset)+1) for x in self.frange(0, 2*math.pi*len(timestamps)/step, 2*math.pi/float(step))]
        return  zip(timestamps, valArg)



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

    def frange(sefl, start, end=None, inc=None):
        if end == None:
            end = start + 0.0
            start = 0.0
        if inc == None:
            inc = 1.0
        L = []
        while 1:
            next = start + len(L) * inc
            if inc > 0 and next >= end:
                break
            elif inc < 0 and next <= end:
                break
            L.append(next)
        return L