# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

import sys,time

sys.path.insert(0, ".")

from RMUtilsFramework.rmLogging import log

##------------------------------------------------------------------------
##
##
class RMCPUStats:
    def __init__(self, statpath = "/proc/stat"):
        self.statpath = statpath

    def get(self):
        with open(self.statpath) as statfile:
            cputimes = statfile.readline()  # Gets only the total cpu time not per core

        user, nice, system, idle, iowait, irq, softrig, steal, guest, guestnice =  (int(t) for t in cputimes.split()[1:]) # generator expression

        user -= guest
        nice -= guestnice

        idleTotal = idle + iowait
        nonIdleTotal = user + nice + system + irq + softrig + steal

        total = nonIdleTotal + idleTotal
        #log.info((user, nice, system, idle, iowait, irq, softrig, steal, guest, guestnice))
        #log.info("Active: %d Idle: %d", nonIdleTotal, idleTotal)

        return { 'active': nonIdleTotal, 'idle': idleTotal }


    def getPercentage(self):
        usage = 0
        try:
            startUsage = self.get()
            time.sleep(1)
            finalUsage = self.get()
            try:
                prevActive = startUsage['active']
                prevIdle = startUsage['idle']
                active = finalUsage['active']
                idle = finalUsage['idle']

                deltaActive = active - prevActive
                deltaIdle = idle - prevIdle

                usage = (float(deltaActive) / (deltaActive + deltaIdle)) * 100
            except ZeroDivisionError:
                pass

        except Exception, e:
            log.error("Cannot read cpu stats from %s because %s" % (self.statpath, str(e)))

        return usage

#-----------------------------------------------------------------------------------------------------------
# Main Test Unit
#
if __name__ == "__main__":
    log.info("CPU Utilisation: %.2f" % RMCPUStats().getPercentage())
