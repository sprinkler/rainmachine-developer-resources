# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from rmWeatherData import RMWeatherData

class RMMixerData(RMWeatherData):
    def __init__(self, timestamp = None, useCounters = False):
        RMWeatherData.__init__(self, timestamp, useCounters)

        self.minTemp = None
        self.maxTemp = None

        self.minRH = None
        self.maxRH = None

        self.et0calc = None
        self.et0final = None

    def activateCounters(self):
        RMWeatherData.activateCounters(self)
        self.minTempCounter = 0
        self.maxTempCounter = 0
        self.minRHCounter = 0
        self.maxRHCounter = 0

    def toString(self):
        if self.useCounters:
            text = ", minTemp=" + `self.minTemp` + "/" + `self.minTempCounter` + \
                    ", maxtTemp=" + `self.maxTemp` + "/" + `self.maxTempCounter` + \
                    ", minRH=" + `self.minRH` + "/" + `self.minRHCounter` + \
                    ", maxRH=" + `self.maxRH` + "/" + `self.maxRHCounter` + \
                    ", et0cal=" + `self.et0calc` + ", et0final=" + `self.et0final`
        else:
            text = ", minTemp=" + `self.minTemp` + \
                    ", maxtTemp=" + `self.maxTemp` + \
                    ", minRH=" + `self.minRH` + \
                    ", maxRH=" + `self.maxRH` + \
                    ", et0cal=" + `self.et0calc` + ", et0final=" + `self.et0final`

        return RMWeatherData.toString(self) + text
