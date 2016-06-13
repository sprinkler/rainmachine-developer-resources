# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

import sys,time
from RMUtilsFramework.rmTimeUtils import *

sys.path.insert(0, ".")

from RMUtilsFramework.rmLogging import log

class RMRainSensor:
    def __init__(self, sensorPath = None):
        self._rainSensorPath = "/sys/devices/platform/rmsensor/raindetected"  # simple 0/1 from kernel module

        if sensorPath is None:
            self.sensorPath = self._rainSensorPath
        else:
            self.sensorPath = sensorPath

    def check(self, normallyClosed = True):
        rainDetected = False

        try:
            with open(self.sensorPath) as f:
                tmp = int(f.readline().strip())
                if tmp == 1:
                    rainDetected = True
        except:
            pass
            #log.debug("RainSensor doesn't exists or returns invalid data")

        # By default rainsensor kernel module reports 1 on short if normallyClosed is true then short means no rain
        # we flip the value below based on this setting
        return (rainDetected ^ normallyClosed)

class RMRainSensorSoftware:
    def __init__(self):
        self.__dayQPF = {}  # table with day timestamp and its QPF

    def setDayQPF(self, dayTimestamp, qpf):
        if not dayTimestamp is None:
            self.__dayQPF[dayTimestamp] = qpf
            log.debug("Setting qpf %f for day: %d(%s)" %  (qpf, dayTimestamp, rmTimestampToDateAsString(dayTimestamp)))

    def clearDayQPF(self):
        self.__dayQPF = {}

    def check(self, minQPF, timestamp=None):

        if timestamp is None:
            timestamp = rmCurrentDayTimestamp()
        else:
            timestamp = rmGetStartOfDay(timestamp)

        dayQPF = self.__dayQPF.get(timestamp, None)

        if dayQPF is not None and dayQPF > minQPF:
            return True

        return False


if __name__ == "__main__":
    s = RMRainSensor()
    log.info("Rain Detected: " + ("No", "Yes")[s.get()])
