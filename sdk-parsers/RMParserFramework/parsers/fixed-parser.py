# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMParserFramework.rmParserManager import RMParserManager

class FixedParser(RMParser):
    parserName = "Fixed Parser"
    parserDescription = "A parser that only output fixed values for testing"
    parserForecast = True
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600

    params = {  "qpfValues" : '0, 0, 0, 0, 0, 0,'
                              '0, 0, 0, 0, 0, 0,'
                              '0.1, 0.1, 0.1, 0.1, 0.1, 0.1,'
                              '0, 0, 0, 0, 0, 0,'
                              '0, 0, 0, 0, 0, 0,'
                              '0.1, 0.1, 0.1, 0.1, 0.1, 0.1,'
                              '0, 0, 0, 0, 0, 0', #past value is rain
                "temperatureValues" : '10, 20, 30, 30, 20, 10,'
                                      '10, 20, 30, 30, 20, 10,'
                                      '10, 20, 30, 30, 20, 10,'
                                      '10, 20, 30, 30, 20, 10,'
                                      '10, 20, 30, 30, 20, 10,'
                                      '10, 20, 30, 30, 20, 10,'
                                      '10, 20, 30, 30, 20, 10',
                "startTimestamp": "",
            }
    # "et0Values" : ' 0.3, 0.3, 0.3, 0.3, 0.3, 0.3,'
    #                           ' 0.4, 0.4, 0.4, 0.4, 0.4, 0.4,'
    #                           ' 0.3, 0.3, 0.3, 0.3, 0.3, 0.3,'
    #                           ' 0.2, 0.2, 0.2, 0.2, 0.2, 0.2,'
    #                           ' 0.3, 0.3, 0.3, 0.3, 0.3, 0.3,'
    #                           ' 0.3, 0.3, 0.3, 0.3, 0.3, 0.3,'
    #                           ' 0.4, 0.4, 0.4, 0.4, 0.4, 0.4',

    def perform(self):
        startDayTimestamp = rmCurrentDayTimestamp()

        noOfDays = 6
        observationsPerDay = 6


        arrQPF = self.params.get("qpfValues")
        arrQPF = arrQPF.split(',')
        arrQPF = [float(item.strip()) for item in arrQPF]
        # arrEt0 = self.params.get("et0Values")
        # arrEt0 = arrEt0.split(',')
        # arrEt0 = [float(item.strip()) for item in arrEt0]
        arrTemp = self.params.get("temperatureValues")
        arrTemp = arrTemp.split(',')
        arrTemp = [float(item.strip()) for item in arrTemp]

        startTS = self.params.get("startTimestamp")

        if startTS is None or startTS == 0 or startTS=='':
            #first run
            startTS = startDayTimestamp - 24*3600 # set for yesterday
            self.params["startTimestamp"] = str(startTS)
            parserManager = RMParserManager.instance
            parserID = parserManager.parserTable.getParserIdByName(self.parserName)
            parserManager.parserTable.updateParserParams(parserID, self.params)



        startTS = int(startTS)

        arrTimestamps = [x for x in range(startDayTimestamp-24*3600, startDayTimestamp+noOfDays*24*3600, 4*3600)]

        yestedayTS = startDayTimestamp - 24*3600

        yesterdayIdx = (yestedayTS - startTS)/(4*3600)

        #qpf is rain
        if len(arrQPF) <= 0:
            return

        yRain = 0
        yMinTemp = 1000
        yMaxTemp = -1000
        # yEt0 = 0
        yQpf = 0

        # idx = arrTimestamps.index(lastTs)
        for idxnm in range(yesterdayIdx, yesterdayIdx + observationsPerDay):
            idx = self._getIdx(idxnm, len(arrTimestamps))
            yRain += arrQPF[idx]
            yMaxTemp = max(yMaxTemp, arrTemp[idx])
            yMinTemp = min(yMinTemp, arrTemp[idx])
            # yEt0 += arrEt0[idx]
        # yEt0 = yEt0 / observationsPerDay

        self.addValue(RMParser.dataType.MINTEMP, yestedayTS, yMinTemp)
        self.addValue(RMParser.dataType.MAXTEMP, yestedayTS, yMaxTemp)
        self.addValue(RMParser.dataType.RAIN, yestedayTS, yRain)
        # self.addValue(RMParser.dataType.ET0, yestedayTS, yEt0)

        todayTS = arrTimestamps.index(startDayTimestamp)

        idxRange = range(yesterdayIdx + observationsPerDay, yesterdayIdx+(noOfDays+1)*observationsPerDay)
        i = todayTS
        for idxnm in idxRange:
            idx = self._getIdx(idxnm, len(arrTimestamps) )
            yQpf = arrQPF[idx]
            yTemp = arrTemp[idx]
            # yEt0 = arrEt0[idx]
            self.addValue(RMParser.dataType.TEMPERATURE, arrTimestamps[i], yTemp)
            self.addValue(RMParser.dataType.QPF, arrTimestamps[i], yQpf)
            # self.addValue(RMParser.dataType.ET0, arrTimestamps[i], yEt0)
            i += 1

    def _getIdx(self, idx, mod):
        return  (idx+mod)%mod