# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *

class FixedParser(RMParser):
    parserName = "Fixed Parser"
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600

    params = {  "qpfValues" : [1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,41,42], #past value is rain
                "et0Values" : [1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,41,42],
                "temperatureValues" : [1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,1, 2, 3, 4, 5, 6, 7, 8, 9, 0,41,42],
                "startTimestamp": None,
            }

    def perform(self):
        startDayTimestamp = rmCurrentDayTimestamp()

        noOfDays = 6
        observationsPerDay = 6
        arrTimestamps = [x for x in range(startDayTimestamp-24*3600, startDayTimestamp+noOfDays*24*3600, 4*3600)]

        arrQPF = self.params.get("qpfValues")
        arrEt0 = self.params.get("et0Values")
        arrTemp = self.params.get("temperatureValues")

        startTS = self.params.get("startTimestamp")

        if startTS is None or startTS == 0:
            #first run
            startTS = startDayTimestamp - 24*3600 # set for yesterday
            self.params["startTimestamp"] = startTS

        yestedayTS = startDayTimestamp - 24*3600

        yesterdayIdx = arrTimestamps.index(yestedayTS)

        #qpf is rain
        if len(arrQPF) <= 0:
            return

        yRain = 0
        yMinTemp = 1000
        yMaxTemp = -1000
        yEt0 = 0
        yQpf = 0

        # idx = arrTimestamps.index(lastTs)
        for idxnm in range(yesterdayIdx, yesterdayIdx + observationsPerDay):
            idx = self._getIdx(idxnm, len(arrTimestamps))
            yRain += arrQPF[idx]
            yMaxTemp = max(yMaxTemp, arrTemp[idx])
            yMinTemp = min(yMinTemp, arrTemp[idx])
            yEt0 += arrEt0[idx]
        yEt0 = yEt0 / observationsPerDay

        self.addValue(RMParser.dataType.MINTEMP, yestedayTS, yMinTemp)
        self.addValue(RMParser.dataType.MAXTEMP, yestedayTS, yMaxTemp)
        self.addValue(RMParser.dataType.RAIN, yestedayTS, yRain)
        self.addValue(RMParser.dataType.ET0, yestedayTS, yEt0)

        todayTS = arrTimestamps.index(startDayTimestamp)

        for idxnm in range(todayTS, todayTS+noOfDays*observationsPerDay):
            idx = self._getIdx(idxnm, len(arrTimestamps) )
            yQpf = arrQPF[idx]
            yTemp = arrTemp[idx]
            yEt0 = arrEt0[idx]
            self.addValue(RMParser.dataType.TEMPERATURE, arrTimestamps[idx], yTemp)
            self.addValue(RMParser.dataType.QPF, arrTimestamps[idx], yQpf)
            self.addValue(RMParser.dataType.ET0, arrTimestamps[idx], yEt0)


    def _getIdx(self, idx, mod):
        return  (idx+mod)%mod