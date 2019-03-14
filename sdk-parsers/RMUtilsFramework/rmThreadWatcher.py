# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import thread, time, sys, os
from threading import Thread, Lock, current_thread
import ctypes
from fcntl import ioctl

from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp, rmTimestampToDateAsString
from RMUtilsFramework.rmUtils import rmRebootMachineOrApp

class RMThreadWatcher(Thread):

    #----------------------------------------------------------------------------------------
    #
    #
    #
    instance = None

    @staticmethod
    def createInstance():
        if RMThreadWatcher.instance is None:
            RMThreadWatcher.instance = RMThreadWatcher()
            RMThreadWatcher.instance.start()
        return RMThreadWatcher.instance.isAlive()

    #----------------------------------------------------------------------------------------
    #
    #
    #
    NameHintKey = 1
    TimeoutHintKey = 2
    LastUpdateKey = 3

    def __init__(self):
        Thread.__init__(self)
        self.__running = False
        self.__lock = Lock()
        self.__data = {} # key=threadId, value={timeoutHint: timestamp, lastUpdate: timestamp}

        self.__watchDogFile = "/dev/watchdog"
        self.__watchDogDescriptor = None
        self.__watchDogTimeout = 5

        self.__lastWatchdogTimestamp = None
        self.__lastCheckTimestamp = None
        self.__lastNoneIpTimestamp = None
        self.__pause = False

        self.__wifiRefreshTimeout = 60 * 2
        self.__wifiNoneIpTimeout = 60 * 1
        self.__systemTimeChangeThreshold = 60 * 10 # on which system time change(ntpd) threshold we should reset

        self.__mainManager = None

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def registerThread(self, nameHint, timeoutHint):
        ### Call this method from the thread you want to register.
        with self.__lock:
            entry = self.__getThreadEntry(thread.get_ident(), True)
            entry[RMThreadWatcher.NameHintKey] = nameHint
            entry[RMThreadWatcher.TimeoutHintKey] = timeoutHint

    def unregisterThread(self):
        ### Call this method from the thread you want to unregister.
        with self.__lock:
            key = thread.get_ident()
            entry = self.__data.pop(key, None)
            if entry is None:
                log.error("Thread key %s not found. unregister failed" % key)
                return False
            return True


    def updateThread(self):
        ### Call this method from the thread you want to update.
        with self.__lock:
            entry = self.__getThreadEntry(thread.get_ident(), True)
            entry[RMThreadWatcher.LastUpdateKey] = rmCurrentTimestamp()

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def setMainManager(self, mainManager):
        self.__mainManager = mainManager

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def start(self):
        if not self.__running:
            self.__running = True
            Thread.start(self)

    def pause(self):
        self.__pause = True

    def resume(self):
        if self.__pause:
            self.__lastWatchdogTimestamp = None
            self.__lastCheckTimestamp = None
            self.__pause = False

    def stop(self):
        self.__running = False

    def run(self):

        restartApp = False

        while self.__running:
            #if RMOSPlatform().AUTODETECTED != RMOSPlatform.SIMULATED:
            #    self.__refreshWatchDog()

            if not self.__pause and self.__lock.acquire(False):
                try:
                    if self.__checkFactoryReset():
                        break

                    if not self.__checkThreads():
                        restartApp = True
                        break

                except Exception, e:
                    log.error(e)
                finally:
                    self.__lock.release()

            time.sleep(2)

        if restartApp:
            self.__restartApp()

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def __restartApp(self):
        rmRebootMachineOrApp(False, 777)

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def __checkFactoryReset(self):
        factoryReset = os.path.exists("/tmp/factory-reset")
        if factoryReset and self.__mainManager:
            try:
                os.remove("/tmp/factory-reset")
            except Exception, e:
                log.error(e)
            self.__mainManager.factoryReset()
        return factoryReset

    def __checkThreads(self):

        timestamp = rmCurrentTimestamp()

        # Work around for a system date change
        resetWatcher = not self.__lastCheckTimestamp is None and \
                       abs(timestamp - self.__lastCheckTimestamp) >= self.__systemTimeChangeThreshold

        everythingOk = True

        if resetWatcher:
            fromTime = rmTimestampToDateAsString(self.__lastCheckTimestamp) if self.__lastCheckTimestamp else None
            toTime = rmTimestampToDateAsString(timestamp)

            log.warning("System time has changed (from %s, to %s)! Resetting thread watcher!" % (fromTime, toTime))

            self.__lastWatchdogTimestamp = None
            for threadId in self.__data:
                details = self.__getThreadEntry(threadId)
                details[RMThreadWatcher.LastUpdateKey] = None

            if self.__mainManager:
                self.__mainManager.systemDateTimeChanged()
        else:

            for threadId in self.__data:
                details = self.__getThreadEntry(threadId)

                timeoutHint = details[RMThreadWatcher.TimeoutHintKey]
                lastUpdate = details[RMThreadWatcher.LastUpdateKey]

                if timeoutHint is None:
                    log.debug("Thread %d (%s) has no timeout hint!" % (threadId, details[RMThreadWatcher.NameHintKey]))
                elif lastUpdate is None:
                    log.debug("Thread %d (%s) is not started yet!" % (threadId, details[RMThreadWatcher.NameHintKey]))
                elif timeoutHint < (timestamp - lastUpdate):
                    everythingOk = False
                    log.debug("Thread %d (%s) didn't responde since [%s] (timeoutHint=%d, timeout=%d)!" % \
                              (threadId, details[RMThreadWatcher.NameHintKey], rmTimestampToDateAsString(lastUpdate), timeoutHint, (timestamp - lastUpdate)))

        self.__lastCheckTimestamp = timestamp
        return everythingOk

    def __getThreadEntry(self, threadId, createIfNotExists = False):
        entry = self.__data.get(threadId, None)
        if entry is None and createIfNotExists:
            entry = {RMThreadWatcher.TimeoutHintKey: None, RMThreadWatcher.LastUpdateKey: None}
            self.__data[threadId] = entry
        return entry

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def __refreshWatchDog(self):
        timestamp = rmCurrentTimestamp()

        if self.__lastWatchdogTimestamp is None or (timestamp - self.__lastWatchdogTimestamp) >= self.__watchDogTimeout:
            if self.__watchDogDescriptor is None:
                try:
                    self.__watchDogDescriptor = open(self.__watchDogFile, 'w')
                    log.info("Opened system watchdog file %s with timeout %d" % (self.__watchDogFile, self.__watchDogTimeout))
                except Exception, e:
                    log.error(e)
            try:
                self.__watchDogDescriptor.write(`timestamp`)
                self.__watchDogDescriptor.flush()
                log.debug("PING Hardware Watchdog")
            except Exception, e:
                log.error(e)

            self.__lastWatchdogTimestamp = timestamp

    def __stopWatchdog(self):
        if self.__watchDogDescriptor is not None:
            self.__watchDogDescriptor.write('V') # Magic char = expect close stop timer
            self.__watchDogDescriptor.flush()
            self.__watchDogDescriptor.close()
            self.__watchDogDescriptor = None
            self.__lastWatchdogTimestamp = None
            log.info("Closed system watchdog file %s" % (self.__watchDogFile))


    def __setWatchdogMaxTimeout(self):
            WDIOC_SETTIMEOUT = 0xC0045706 # direction(3 RW) << 30 | size (4 int) << 16 | type ( 'W') << 8 | number (6)
            timeout = ctypes.c_int(120) # seconds
            if self.__watchDogDescriptor is not None:
                fd = self.__watchDogDescriptor.fileno()
                ioctl(fd, WDIOC_SETTIMEOUT, timeout)
                self.__watchDogDescriptor.close()
            else:
                log.error("Can't set watchdog max timeout. Device not opened")


    #----------------------------------------------------------------------------------------
    #
    #
    #
    def __refreshWIFI(self):
        timestamp = rmCurrentTimestamp()
        lastWIFICheckTimestamp = globalWIFI.wifiInterface.lastWIFICheckTimestamp
        oldIP = globalWIFI.wifiInterface.ipAddress

        if lastWIFICheckTimestamp is None or oldIP is None or (timestamp - lastWIFICheckTimestamp) >= self.__wifiRefreshTimeout:
            try:
                globalWIFI.detect()

                if oldIP != globalWIFI.wifiInterface.ipAddress:
                    log.info("Refreshed WIFI Information. (old: %s new ip: %s)" % (`oldIP`, `globalWIFI.wifiInterface.ipAddress`))

                if RMOSPlatform().AUTODETECTED == RMOSPlatform.ANDROID:
                    return

                # Handle None IP
                if globalWIFI.wifiInterface.ipAddress is None:
                    if self.__lastNoneIpTimestamp is None or (timestamp - self.__lastNoneIpTimestamp) < self.__wifiNoneIpTimeout:
                        # First occurrence of None IP     OR    we can wait some more time.
                        if self.__lastNoneIpTimestamp is None:
                            self.__lastNoneIpTimestamp = timestamp
                        log.debug("Refreshed WIFI Information - no IP detected. Give it some more time: %d seconds!" % (self.__wifiNoneIpTimeout - (timestamp - self.__lastNoneIpTimestamp), ))
                        return
                    else:
                        globalWIFI.restart()
                        log.warn("Refreshed WIFI Information - WIFI quick reloaded because no IP detected. New IP is %s" % `globalWIFI.wifiInterface.ipAddress`)

                self.__lastNoneIpTimestamp = None # Reset None IP timestamp.

                # Check if we never connected to this AP, set back AP mode and restart app
                if globalWIFI.wifiInterface.mode == "managed" and not globalWIFI.hasConnectedOnce():
                    if globalWIFI.wifiInterface.hasClientLink:
                        globalWIFI.saveHasConnectedOnce(True)
                    else:
                        log.warning("WIFI Watcher Client IP (%s) configuration failed, restarting in AP mode." % oldIP)
                        globalWIFI.setDefaultAP()
                        globalWIFI.saveHasConnectedOnce(False)
                        globalWIFI.restart()
                        self.__mainManager.touchWakeMessage()

            except Exception, e:
                log.error(e)

    def __dump(self):
        log.debug(self.__data)


