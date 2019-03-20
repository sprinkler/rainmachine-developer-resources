# Copyright (c) 2014-2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>
#          Virgil Dinu <virgil.dinu@coretech.co>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMDataFramework.rmWeatherData import RMWeatherConditions

import datetime, time, urllib, urllib2
import json
import urllib2

class FAWN(RMParser):
    parserName = "FAWN Parser"
    parserDescription = "Florida Automated Weather Network observations"
    parserForecast = False
    parserHistorical = True
    parserEnabled = False
    parserDebug = True
    parserInterval = 6 * 3600
    params = {"station": 480, "useHourly": False}

    def isEnabledForLocation(self, timezone, lat, long):
        if FAWN.parserEnabled and timezone:
            return timezone.startswith("US") or timezone.startswith("America")
        return False

    def perform(self):
        s = self.settings
        URLHourly = "http://fawn.ifas.ufl.edu/controller.php/lastHour/summary/json"
        URLDaily = "http://fawn.ifas.ufl.edu/controller.php/lastDay/summary/json"
        URLParams = []

        useHourly = self.params.get("useHourly", False)
        
        #-----------------------------------------------------------------------------------------------
        #
        # Get hourly data.
        #
        if useHourly:
            try:
                d = self.openURL(URLHourly, URLParams)
                if d is None:
                    return

                json_data = d.read()
                json_data = json_data.replace("'","\"")
                hourly = json.loads(json_data)

                for entry in hourly:
                    # only selected station
                    if int(entry.get("StationID")) == self.params.get("station"):
                        dateString = entry.get("startTime")
                        #timestamp = rmTimestampFromDateAsStringWithOffset(dateString)
                        timestamp = rmTimestampFromDateAsString(dateString[:-6], '%Y-%m-%dT%H:%M:%S')
                        if timestamp is None:
                            log.debug("Cannot convert hourly data startTime: %s to unix timestamp" % dateString)
                            continue

                        # Add 12h in the future for FAWN timestamp to fix badly reported offset and make it middle of the day UTC (Dragos)
                        timestamp += 12 * 60 *60

                        self.addValue(RMParser.dataType.TEMPERATURE, timestamp, self.__toFloat(entry.get("t2m_avg")))
                        self.addValue(RMParser.dataType.MINTEMP, timestamp, self.__toFloat(entry.get("t2m_min")))
                        self.addValue(RMParser.dataType.MAXTEMP, timestamp, self.__toFloat(entry.get("t2m_max")))
                        # km/h -> m/s
                        self.addValue(RMParser.dataType.WIND, timestamp, 0.27777777777778 * self.__toFloat(entry.get("ws_avg")))
                        # cm -> mm
                        self.addValue(RMParser.dataType.RAIN, timestamp, 10 * self.__toFloat(entry.get("rain_sum")))
                        self.addValue(RMParser.dataType.DEWPOINT, timestamp, self.__toFloat(entry.get("dp_avg")))
                        self.addValue(RMParser.dataType.RH, timestamp, self.__toFloat(entry.get("rh_avg")))

                if self.parserDebug:
                    log.debug(self.result)

            except Exception, e:
                log.error("*** Error retrieving hourly data from FAWN")
                log.exception(e)

        #-----------------------------------------------------------------------------------------------
        #
        # Get daily data.
        #
        try:
            d = self.openURL(URLDaily, URLParams)
            if d is None:
                return
            
            json_data = d.read()
            json_data = json_data.replace("'","\"")
            daily = json.loads(json_data)

            for entry in daily:
                # only selected station
                if int(entry.get("StationID")) == self.params.get("station"):
                    dateString = entry.get("startTime")
                    #timestamp = rmTimestampFromDateAsStringWithOffset(dateString)
                    timestamp = rmTimestampFromDateAsString(dateString[:-6], '%Y-%m-%dT%H:%M:%S')
                    if timestamp is None:
                        log.debug("Cannot convert daily data startTime: %s to unix timestamp" % dateString)
                        continue

                    # Add 12h in the future for FAWN timestamp to fix badly reported offset and make it middle of the day UTC (Dragos)
                    timestamp += 12 * 60 *60

                    self.addValue(RMParser.dataType.TEMPERATURE, timestamp, self.__toFloat(entry.get("t2m_avg")))
                    self.addValue(RMParser.dataType.MINTEMP, timestamp, self.__toFloat(entry.get("t2m_min")))
                    self.addValue(RMParser.dataType.MAXTEMP, timestamp, self.__toFloat(entry.get("t2m_max")))
                    # km/h -> m/s
                    self.addValue(RMParser.dataType.WIND, timestamp, 0.27777777777778 * self.__toFloat(entry.get("ws_avg")))
                    # cm -> mm
                    self.addValue(RMParser.dataType.RAIN, timestamp, 10 * self.__toFloat(entry.get("rain_sum")))
                    self.addValue(RMParser.dataType.DEWPOINT, timestamp, self.__toFloat(entry.get("dp_avg")))
                    self.addValue(RMParser.dataType.RH, timestamp, self.__toFloat(entry.get("rh_avg")))
                    self.addValue(RMParser.dataType.MINRH, timestamp, self.__toFloat(entry.get("rh_min")))
                    self.addValue(RMParser.dataType.MAXRH, timestamp, self.__toFloat(entry.get("rh_max")))
                    # in -> mm
                    self.addValue(RMParser.dataType.ET0, timestamp, 25.4 * self.__toFloat(entry.get("et")))

            if self.parserDebug:
                log.debug(self.result)
                
        except Exception, e:
            log.error("*** Error retrieving daily data from FAWN")
            log.exception(e)

    def __toFloat(self, value):
        if value is None:
            return value
        return float(value)
