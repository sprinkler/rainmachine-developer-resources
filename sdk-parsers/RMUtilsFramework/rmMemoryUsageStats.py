# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

import sys,resource

sys.path.insert(0, ".")

from RMUtilsFramework.rmLogging import log

##------------------------------------------------------------------------
##
##
class RMMemoryUsageStats():
    def __init__(self, statpath = '/proc/self/status'):
        self.statpath = statpath

    def getFromProc(self):
        status = None
        result = {'peak': 0, 'rss': 0}
        try:
            status = open(self.statpath)
            for line in status:
                parts = line.split()
                key = parts[0][2:-1].lower()
                if key in result:
                    result[key] = int(parts[1])
        except (IOError, OSError):
            log.debug("Cannot get memory stats from /proc")
        finally:
            if status is not None:
                status.close()
        return result

    def getFromPyResource(self):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    def dump(self):
        log.info("Memory Usage Stats")
        log.info("------------------------------------------------------")
        log.info("As reported by pyresource %d " % self.getFromPyResource())
        m = self.getFromProc()
        log.info("As reported by /proc peak: %d rss: %d" % (m["peak"], m["rss"]))


#-----------------------------------------------------------------------------------------------------------
# Main Test Unit
#
if __name__ == "__main__":
    RMMemoryUsageStats().dump()
