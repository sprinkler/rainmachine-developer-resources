# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from functools import wraps
import errno
import os
import signal
import urllib, urllib2, ssl
import sys
import datetime

from RMDataFramework.rmWeatherData import *
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmCurrentDayTimestamp, rmGetStartOfDayUtc
from RMFormulaFramework.formula import asceDaily
USE_THREADING__ = False
ALLOW_HISTORIC_PARSERS = True

class RMTimeoutError(Exception):
    pass

def _handle_timeout(signum, frame):
    error_message = os.strerror(errno.ETIME)
    log.error("*** Timeout occurred while running a parser: %s" % error_message)
    raise RMTimeoutError(error_message)

class RMParserType(type):
    def __init__(cls, name, bases, attrs):
            super(RMParserType, cls).__init__(name, bases, attrs)
            if not hasattr(cls, "parsers"):
                cls.parsers = []
            else:
                cls.registerParser(cls)

            # Add timeout to perform function
            if hasattr(cls, "perform"):
                def timedPerform(self):
                    global USE_THREADING__
                    if not USE_THREADING__:
                        seconds = 10 * 60
                        _old_handler = signal.signal(signal.SIGALRM, _handle_timeout)
                        signal.alarm(seconds)
                    try:
                        result = attrs["perform"](self)
                    except RMTimeoutError, e:
                        log.error("*** Timeout occurred while running parser %s" % self.parserName)
                        log.exception(e)
                        return None
                    finally:
                        if not USE_THREADING__:
                            signal.alarm(0)
                            signal.signal(signal.SIGALRM, _old_handler)

                    return result

                setattr(cls, "perform", timedPerform)

    def registerParser(cls, parser):
        try:
            instance = parser()
            #for prs in cls.parsers:
            #   if instance.__class__.__name__ is prs.__class__.__name__:
            #       raise Exception("Parser allready exists")
            #       return
            cls.parsers.append(instance)
            log.info("*** Registering parser %s with interval %d" % (instance.parserName, instance.parserInterval))
        except:
            log.info("*** Registering parser %s failed")

class RMParser(object):
    __metaclass__ = RMParserType

    (
        RuntimeDayTimestamp,
    ) = range(0, 1)

    parserName = "Unknown"
    parserDescription = "Base class"
    parserForecast = False
    parserHistorical = False
    parserInterval = 60 * 60 * 3
    parserEnabled = False
    parserDebug = False
    params = {}

    userDataTypes = []
    dataType = RMWeatherDataType
    conditionType = RMWeatherConditions
    lastKnownError = ''
    isRunning = False

    def __init__(self):
        self.result = {}
        self.settings = {} #set from parserManager
        self.runtime = {RMParser.RuntimeDayTimestamp: 0}

    def isEnabledForLocation(self, timezone, lat, long):
        return False

    def perform(self):
        log.warning("*** Perform method not implemented by parser '%s'" % self.parserName)

    def openURL(self, url, params = None, encodeParameters = True, headers = {}):
        if params:
            if encodeParameters:
                query_string = urllib.urlencode(params)
            else:
                query_string = params

            url = "?" . join([url, query_string])

        log.debug("Parser '%s': downloading from %s" % (self.parserName, url))

        try:
            req = urllib2.Request(url=url, headers=headers)
            res = urllib2.urlopen(url=req, timeout=60)
            return res
        except Exception, e:
            if hasattr(ssl, '_create_unverified_context'): #for mac os only in order to ignore invalid certificates
                try:
                    context = ssl._create_unverified_context()
                    res = urllib2.urlopen(url=req, timeout=60, context=context)
                    return res
                except Exception, e:
                    log.error("*** Error in parser '%s' while downloading data from %s, error: %s" % (self.parserName, url, e))
                    self.lastKnownError = "Error: Can not open url"
                    log.exception(e)
                    return None
            else:
                log.error("*** Error in parser '%s' while downloading data from %s, error: %s" % (self.parserName, url, e))
                self.lastKnownError = "Error: Can not open url"
        return None

    def addValue(self, key,timestamp, value, roundToHour = True):
        if timestamp == None:
            log.error("*** Parser '%s': error adding single value - ignoring None timestamp!" % self.parserName)
            return

        timestamp = timestamp - (timestamp % 3600)
        if ALLOW_HISTORIC_PARSERS or self.runtime[RMParser.RuntimeDayTimestamp] < timestamp:
            if timestamp not in self.result:
                self.result[timestamp] = RMWeatherData(timestamp)
            self.result[timestamp].setValue(key, value)
            #log.debug("%d added value %s" % (timestamp, value))

    def addValues(self, key, timestampsWithValues, roundToHour = True):
        for entry in timestampsWithValues:
            if len(entry)  == 2:
                timestamp = entry[0]
                value = entry[1]

                if timestamp == None:
                    log.error("*** Parser '%s': error adding multiple values - ignoring None timestamp!" % self.parserName)
                    continue

                timestamp = timestamp - (timestamp % 3600)

                if ALLOW_HISTORIC_PARSERS or self.runtime[RMParser.RuntimeDayTimestamp] < timestamp:
                    if timestamp not in self.result:
                        self.result[timestamp] = RMWeatherData(timestamp)
                    self.result[timestamp].setValue(key, value)

    def addUserValue(self, key,timestamp, value, roundToHour = True):
        if timestamp == None:
            log.error("*** Parser '%s': error adding user value - ignoring None timestamp!" % self.parserName)
            return

        timestamp = timestamp - (timestamp % 3600)
        if self.runtime[RMParser.RuntimeDayTimestamp] < timestamp:
            if timestamp not in self.result:
                self.result[timestamp] = RMWeatherData(timestamp)
            self.result[timestamp].setUserValue(key, value)

    def clearValues(self):
        self.result.clear()

    def hasValues(self):
        return (self.result and True) or False

    def getValues(self):
        return self.result.values()

    def dump(self):
        log.debug("%s" % (self.result))