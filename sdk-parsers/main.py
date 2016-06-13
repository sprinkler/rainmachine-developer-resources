# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import signal, sys, os, time

sys.path.insert(0, os.path.dirname(__file__))

from RMDataFramework.rmUserSettings import globalSettings
from RMDatabaseFramework.rmDatabaseManager import globalDbManager
from RMCore.rmMainManager import RMMainManager
from RMUtilsFramework.rmCommandThread import RMCommandThread
from RMUtilsFramework.rmLogging import log, logvolatile
from RMUtilsFramework import rmUtils, rmTimeUtils
from RMUtilsFramework.rmMemoryUsageStats import RMMemoryUsageStats


##------------------------------------------------------------------------
##
##

globalSettings.parseSysArguments(True)

# Default log (persistent)
#log.setConsoleLogLevel() # Reduce console output level to ERROR by default
log.enableFileLogging(os.path.join(globalSettings.databasePath, "log/rainmachine.log"))

#globalGPIO.turnOnOffAllLeds(True)

log.info("RainMachine SDK Copyright (c) 2015 Green Electronics LLC")
#log.info("---------------------------------------- USAGE ----------------------------------------------")
#log.info(" python %s" % (__file__))
#log.info(" python %s name,lat,long,et0avg [httpServerPort]" % (__file__))
#log.info("---------------------------------------------------------------------------------------------")


##------------------------------------------------------------------------
##  Shutdown handler for SIGINT signal
##
def mainShutdownHandler(signal, frame):
    log.info(">>>>>>> Got interrupt signal shutting down ...")
    RMMainManager.instance.stop()

##------------------------------------------------------------------------
## Global message queue for threads
##
if not RMCommandThread.createInstance():
    log.error("Error initializing Command Thread")
    exit(2)

##------------------------------------------------------------------------
## Check for first run as we need to initialise at least default zones
##
globalSettings.firstRun = not os.path.isfile(os.path.join(globalSettings.databasePath, 'rainmachine-main.sqlite'))


##------------------------------------------------------------------------
## Global Database Descriptors
##
globalDbManager.initialize(globalSettings.databasePath)

##------------------------------------------------------------------------

if not RMMainManager.createInstance():
    log.error("Error initializing Main Manager")
    exit(2)

globalSettings.dumpInfo()

signal.signal(signal.SIGINT, mainShutdownHandler)

##------------------------------------------------------------------------
## START UP EVERYTHING
##
RMMainManager.instance.run()



##------------------------------------------------------------------------
##
globalDbManager.uninitialize()

RMCommandThread.instance.stop()
RMCommandThread.instance.join()

##------------------------------------------------------------------------
##
## Show memory stats before restart/reboot
RMMemoryUsageStats().dump()
