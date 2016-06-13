# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import os, sys, socket, struct
import time
from datetime import timedelta

#import inspect

sys.path.insert(0, ".")

from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp, rmTimestampToDateAsString
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmCPUStats import RMCPUStats
from RMUtilsFramework.rmMemoryUsageStats import RMMemoryUsageStats
from RMUtilsFramework.rmUtils import getAlarmElapsedRealTime
from RMOSGlue.rmOSPlatform import RMOSPlatform
from RMOSGlue.rmWireless import globalWIFI

class RMMachineDiag:
    def __init__(self):
        self.lastCheck = 0

        self.__bootCompleted = True
        self.__networkStatus = False  # True if it can detect a gateway address
        self.__internetStatus = False # True if it can connect to an outside address
        self.__locationStatus = False
        self.__weatherStatus = False
        self.__timeStatus = False
        self.__hasWifi = False
        self.__cpuUsage = 0
        self.__memoryUsage = 0
        self.__uptimeString = ""
        self.__uptimeSeconds = 0
        self.__networkGateway = None
        self.__cloudStatus = -1

        self.checkMachine()


    def checkMachine(self, checkNetwork = True, checkLocation = True, checkWeather = True, checkTime = True):
        if checkNetwork:
            self.__diagNetwork()
            self.__diagInternet()

        if checkLocation:
            self.__diagLocation()

        if checkWeather:
            self.__diagWeather()

        if checkTime:
            self.__diagTime()

        self.__diagWifi()
        self.__diagCloud()

        self.__cpuUsage = RMCPUStats().getPercentage()
        self.__uptimeSeconds = self.getUptime()
        self.__uptimeString = str(timedelta(seconds = self.__uptimeSeconds))
        self.__memoryUsage = RMMemoryUsageStats().getFromProc()['rss']

        self.lastCheck = rmCurrentTimestamp()

        return self.__networkStatus, self.__locationStatus, self.__weatherStatus, self.__timeStatus

    def getStatus(self):
        return {
            "lastCheck": rmTimestampToDateAsString(self.lastCheck),
            "lastCheckTimestamp": self.lastCheck,
            "bootCompleted": self.__bootCompleted,
            "networkStatus": self.__networkStatus,
            "internetStatus": self.__internetStatus,
            "cloudStatus":  self.__cloudStatus,
            "locationStatus": self.__locationStatus,
            "weatherStatus": self.__weatherStatus,
            "timeStatus": self.__timeStatus,
            "hasWifi": self.__hasWifi,
            "softwareVersion": globalSettings.softwareVersion,
            "wizardHasRun": globalSettings.wizardHasRun,
            "standaloneMode": globalSettings.standaloneMode,
            "wifiMode": globalWIFI.wifiInterface.mode,
            "cpuUsage": self.__cpuUsage,
            "memUsage": self.__memoryUsage,
            "uptime": self.__uptimeString,
            "uptimeSeconds": self.__uptimeSeconds,
            "gatewayAddress": self.__networkGateway
        }

    def getUptime(self):
        uptimeSeconds = 0
        if RMOSPlatform().AUTODETECTED == RMOSPlatform.ANDROID:
            uptimeSeconds = getAlarmElapsedRealTime()
        else:
            try:
                with open('/proc/uptime') as f:
                    procLine = f.readline().split()[0]

                uptimeSeconds = int(float(procLine))
            except (IOError, OSError):
                log.debug("Cannot get platform uptime.")

        return uptimeSeconds

    def __diagTime(self):
        now = int(time.time())
        if now < 1349067600: # 2012 year
            self.__timeStatus = False
        else:
            self.__timeStatus = True

    # TODO: see RMUserSettings.validateLocationSettings
    def __diagLocation(self):
        self.locationStatus = False

        l = globalSettings.getSettings().location
        if l is None:
            return
        if l.latitude is None or l.longitude is None:
            return
        if l.elevation is None:
            return
        if l.et0Average is None:
            return

        self.__locationStatus = True

    def __diagNetwork(self):
        try:
            with open("/proc/net/route") as f:
                for line in f:
                    fields = line.strip().split()
                    if fields[1] != "00000000": # default gateway destination 0.0.0.0
                        continue
                    #log.debug(fields)
                    if int(fields[3], 16) & 2: # check route to be UG from the third field which is in base16
                        self.__networkStatus = True
                        try:
                            self.__networkGateway = socket.inet_ntoa(struct.pack("=L", int(fields[2], 16)))
                            #self.__networkGateway = ".".join([str(int(fields[2][i:i+2], 16)) for i in range(0, len(fields[2]), 2)]) # depends on endianess
                        except:
                            self.__networkGateway = None
                            log.debug("Cannot get gateway address.")

                        log.debug("Network gateway (%s) up on interface %s" % (self.__networkGateway, fields[0]))
                        return
        except:
            log.error("Cannot find /proc entry for network diag")

        self.__networkStatus = False

    def __diagWifi(self):
        try:
            with open("/proc/net/wireless") as f:
                for line in f:
                    fields = line.strip().split()
                    #log.debug(fields)
                    if not fields[0].endswith(":"):
                        continue

                    log.debug("Wireless interface %s up" % fields[0])
                    self.__hasWifi = True
                    return
        except:
            log.error("Cannot find /proc entry for wireless diag")


        self.__hasWifi= False

    def __diagWeather(self):
        self.__weatherStatus = True

    def __diagInternet(self):
        self.__internetStatus = False
        try:
            ret = os.system("ping -c 1 -w 2 8.8.8.8 > /dev/null 2>&1")
            self.__internetStatus = True if ret == 0 else False
        except Exception, e:
            pass

    def __diagCloud(self):
        self.__cloudStatus = -1
        try:
            with open(globalSettings.cloud._statusFile, 'r') as f:
                try:
                    status = f.readline().rstrip()
                    self.__cloudStatus = int(status)
                except:
                    pass
        except (IOError, OSError):
            pass


globalMachineDiag = RMMachineDiag()

if __name__ == "__main__":
    #curframe = inspect.currentframe()
    #calframe = inspect.getouterframes(curframe, 2)
    #print 'caller name:', calframe[1][3]
    log.info("Testing MachineDiag")
    globalMachineDiag.checkMachine()
    print globalMachineDiag.getStatus()



