# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

import logging
import logging.handlers
import os
import gzip
import time
import shutil

class RMLogger:

    ENABLE_COMPRESSION = True
    ROTATE_FILE_SIZE = 500000

    def __init__(self, name="RainMachine"):
        self._logFileName = None

        self.stdoutHandler = logging.StreamHandler()
        self.format = logging.Formatter(fmt='%(asctime)s - %(levelname)-5s - %(module)s:%(lineno)s - %(message)s')
        self.stdoutHandler.setFormatter(self.format)

        self.filter = RMLogger.RMLoggerFilter()
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addFilter(self.filter)
        self.logger.addHandler(self.stdoutHandler)
        self.logger.enableFileLogging = self.enableFileLogging
        self.logger.setConsoleLogLevel = self.setConsoleLogLevel

    def setGlobalDebugLevel(self, level = logging.DEBUG):
        self.logger.setLevel(level)

    def setModuleDebugLevel(self, name, level = logging.DEBUG):
        self.filter.modulesLevel[name] = level

    def enableFileLogging(self, fileName = "log/rainmachine.log"):
        self._logFileName = fileName
        self.__checkAndCreateLogDir()
        try:

            if RMLogger.ENABLE_COMPRESSION:
                fileHandler = RMLogger.CompressingRotatingFileHandler(fileName, maxBytes=RMLogger.ROTATE_FILE_SIZE, backupCount=1)
            else:
                fileHandler = logging.handlers.RotatingFileHandler(fileName, maxBytes=RMLogger.ROTATE_FILE_SIZE, backupCount=1)

            fileHandler.setFormatter(self.format)
            self.logger.addHandler(fileHandler)

        except Exception, e:
            self.logger.error("Cannot enable file logging to %s: %s" % (fileName, e))

    def setConsoleLogLevel(self, level = logging.ERROR):
        self.stdoutHandler.setLevel(logging.ERROR)   # Send only errors to console

    def __checkAndCreateLogDir(self):
        dirName = os.path.dirname(self._logFileName)
        if not os.path.exists(dirName):
            os.makedirs(dirName)

    def getFileName(self):
        return self._logFileName

    #----------------------------------------------------------------------------------------
    #
    #
    #
    class RMLoggerFilter(logging.Filter):
        def __init__(self):
            logging.Filter.__init__(self)
            self.modulesLevel = {}
        def filter(self, record):
            moduleLevel = self.modulesLevel.get(record.module)
            if moduleLevel == None or record.levelno >= moduleLevel:
                return True
            return False

    #----------------------------------------------------------------------------------------
    #
    #
    #
    class CompressingRotatingFileHandler(logging.handlers.RotatingFileHandler):

        def __init__(self, *args, **kws):
            logging.handlers.RotatingFileHandler.__init__(self, *args, **kws)

        def doRollover(self):
            logging.handlers.RotatingFileHandler.doRollover(self)

            oldLog = self.baseFilename + ".1"
            with open(oldLog) as log:
                with gzip.open(oldLog + '.gz', 'wb') as compressedLog:
                    compressedLog.writelines(log)

            os.remove(oldLog)



# A class for log files that output on /tmp (which should be tmpfs) it will rotate when older than interval
# to a persistent location

class RMLoggerVolatile(RMLogger):
    def __init__(self):
        self._persistentFileName = None
        RMLogger.__init__(self, name="RainMachineVolatile")
        self.logger.enableFileLogging = self.enableFileLogging
        self.logger.truncate = self.truncate

    def enableFileLogging(self, persistentFileName, fileName = "/tmp/rainmachine-volatile.log", interval=10*60):
        self._logFileName = fileName
        self._persistentFileName = persistentFileName

        try:
            fileHandler = RMLoggerVolatile.TimedRotatingOverwriteFileHandler(persistentFileName, fileName, interval=interval)
            fileHandler.setFormatter(self.format)
            self.logger.addHandler(fileHandler)
        except Exception, e:
            self.logger.error("Cannot enable file logging to %s: %s" % (fileName, e))

    def truncate(self):
        try:
            # This should trigger rollover if needed otherwise will roll over an empty truncated file
            self.logger.info("Truncating")
            handler = self.logger.handlers[1]
            handler.doRollover(noPreserving = True)
        except Exception, e:
            self.logger.error("Error truncating: %s" % e)

    def getPersistentFileName(self):
        return self._persistentFileName

    class TimedRotatingOverwriteFileHandler(logging.handlers.BaseRotatingHandler):

        def __init__(self, persistentFileName, filename, interval=86400, encoding=None,  delay=False):
            logging.handlers.BaseRotatingHandler.__init__(self, filename, 'w', encoding=encoding, delay=delay)
            self.interval = interval
            self.persistentFileName = persistentFileName

            self.lastRotate = int(time.time())
            if os.path.exists(persistentFileName):
                self.lastRotate = int(os.path.getmtime(persistentFileName))

        def shouldRollover(self, record):
            if (int(time.time()) - self.lastRotate) > self.interval:
                return 1
            return 0

        def doRollover(self, noPreserving = False):
            if self.stream:
                self.stream.close()
                self.stream = None

            if noPreserving and os.path.exists(self.baseFilename):
                os.remove(self.baseFilename)
            else:
                if os.path.exists(self.persistentFileName):
                    os.remove(self.persistentFileName)

                if os.path.exists(self.baseFilename):
                    shutil.move(self.baseFilename, self.persistentFileName)
                    self.lastRotate = int(time.time())

#----------------------------------------------------------------------------------------
#
#
#
globalLogger = RMLogger()
globalLogger.setModuleDebugLevel('forecast-io-parser', logging.WARNING)
globalLogger.setModuleDebugLevel('rmParserThread', logging.INFO)
globalLogger.setModuleDebugLevel('rmCommandThread', logging.WARNING)
globalLogger.setModuleDebugLevel('rmGPIOGenericLinux', logging.INFO)

#globalLogger.setModuleDebugLevel('rmMixer', logging.INFO)
#globalLogger.setModuleDebugLevel('rmParser', logging.INFO)
#globalLogger.setModuleDebugLevel('rmParserManager', logging.INFO)
#globalLogger.setModuleDebugLevel('noaa-parser', logging.INFO)
#globalLogger.setModuleDebugLevel('main', logging.INFO)
#globalLogger.setModuleDebugLevel('rmPrograms', logging.INFO)
#globalLogger.setModuleDebugLevel('rmUserSettings', logging.INFO)
#globalLogger.setModuleDebugLevel('rmGPIOGenericLinux', logging.INFO)
#globalLogger.setModuleDebugLevel('rmGPIOOpenWRT', logging.INFO)
#globalLogger.setModuleDebugLevel('rmTouchManager', logging.INFO)
#globalLogger.setModuleDebugLevel('rmTouchGenericLinux', logging.INFO)

globalVolatileLogger = RMLoggerVolatile()

log = globalLogger.logger
logvolatile = globalVolatileLogger.logger

if __name__ == "__main__":
    logvolatile.enableFileLogging("/tmp/rm-persistent.log", fileName = "/tmp/rm-volatile.log", interval=1*60)
    print globalVolatileLogger.getFileName()
    print globalVolatileLogger.getPersistentFileName()
    logvolatile.truncate()
    logvolatile.info("Testing now")
    time.sleep(2)
    logvolatile.info("Testing after 2 sec")
    time.sleep(5)
    logvolatile.info("Testing after 2 + 5 sec")
    logvolatile.truncate()
    logvolatile.info("Testing after 2 + 5 sec (should be alone)")

