# Copyright (c) 2014-2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>
#          Virgil Dinu <virgil.dinu@coretech.co>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmUtils import *
from RMDataFramework.rmWeatherData import RMWeatherConditions

import datetime, time, urllib, urllib2
import json
import csv

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
        station = self.params.get("station", None)

        if station is None:
            self.lastKnownError = "No station number configured."
            log.error(self.lastKnownError)
            return

        res = self.performWithDataFeeds(station)
        if not res:
            self.performWithReport(station)



   #-----------------------------------------------------------------------------------------------
    #
    # Get hourly and daily data using the JSON API data feeds
    #
    def performWithDataFeeds(self, station):
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
                log.info("Retrieving data from: %s" % URLHourly)
                d = self.openURL(URLHourly, URLParams)
                if d is None:
                    return

                json_data = d.read()
                json_data = json_data.replace("'","\"")
                hourly = json.loads(json_data)

                for entry in hourly:
                    # only selected station
                    if int(entry.get("StationID")) == station:
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
                self.lastKnownError = "Error retrieving hourly data."
                log.error(self.lastKnownError)
                log.exception(e)


        #-----------------------------------------------------------------------------------------------
        #
        # Get daily data.
        #
        try:
            log.info("Retrieving data from: %s" % URLDaily)
            d = self.openURL(URLDaily, URLParams)
            if d is None:
                return
            
            json_data = d.read()
            json_data = json_data.replace("'","\"")
            daily = json.loads(json_data)

            for entry in daily:
                # only selected station
                if int(entry.get("StationID")) == station:
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
            self.lastKnownError = "Error retrieving daily data, trying report feed."
            log.error(self.lastKnownError)
            log.exception(e)
            return False

        return True


    def performWithReport(self, station):
        s = self.settings
        self.lastKnownError = ""
        now = time.time()
        URLReport = "https://fawn.ifas.ufl.edu/data/reports/?res" #+ str(now)

        POSTParams = self.__generatePOSTParams(station)

        #-----------------------------------------------------------------------------------------------
        #
        # Get daily data.
        #
        try:
            log.info("Retrieving data from: %s" % URLReport)
            POSTParams = urllib.urlencode(POSTParams)
            req = urllib2.Request(URLReport, data=POSTParams)
            response = urllib2.urlopen(req)
            data = response.read()
        except Exception, e:
            self.lastKnownError = "Cannot download data"
            log.error(self.lastKnownError)
            log.error(e)
            return False

        if data is None:
            return False

        try:
            parsedData = csv.DictReader(data.splitlines())

            # '2m DewPt avg (F)': '62.13',
            # 'RelHum avg 2m (pct)': '81',
            # '2m Rain max over 15min(in)': '0.00',
            # '10m T max (F)': '79.16',
            # '10m Wind min (mph)': '0.00',
            # 'SolRad avg 2m (w/m^2)': '264.22',
            # 'N (# obs)': '96',
            # 'Period': '26 Mar 2019',
            # '10m Wind avg (mph)': '3.70',
            # 'BP avg (mb)': '1015',
            # '10m T min (F)': '60.35',
            # '10m Wind max (mph)': '14.28',
            # '10m T avg (F)': '69.24',
            # 'WDir avg 10m (deg)': '317',
            # '2m Rain tot (in)': '0.00',
            # 'FAWN Station': 'North Port',
            # 'ET (in)': '0.14'

            for entry in parsedData:
                timestamp = rmTimestampFromDateAsString(entry['Period'], "%d %b %Y")
                self.addValue(RMParser.dataType.TEMPERATURE, timestamp, convertFahrenheitToCelsius(entry['10m T avg (F)']))
                self.addValue(RMParser.dataType.MINTEMP, timestamp, convertFahrenheitToCelsius(entry['10m T min (F)']))
                self.addValue(RMParser.dataType.MAXTEMP, timestamp, convertFahrenheitToCelsius(entry['10m T max (F)']))
                self.addValue(RMParser.dataType.RAIN, timestamp, convertInchesToMM(entry['2m Rain tot (in)']))
                self.addValue(RMParser.dataType.DEWPOINT, timestamp, convertFahrenheitToCelsius(entry[ '2m DewPt avg (F)']))
                self.addValue(RMParser.dataType.RH, timestamp, self.__toInt(entry['RelHum avg 2m (pct)']))
                self.addValue(RMParser.dataType.ET0, timestamp, convertInchesToMM(entry['ET (in)']))
                self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, convertRadiationFromWattsToMegaJoules(entry['SolRad avg 2m (w/m^2)']))

                wind = self.__toFloat(entry['10m Wind avg (mph)'])
                if wind is not None:
                    wind = 0.44704 * wind # mph to mps
                self.addValue(RMParser.dataType.WIND, timestamp, wind)

            if self.parserDebug:
                log.debug(self.result)

        except Exception, e:
            self.lastKnownError = "Error parsing last observed data from FAWN"
            log.error(self.lastKnownError)
            log.exception(e)
            return False

        return True


    def __toFloat(self, value):
        if value is None:
            return value
        return float(value)

    def __toInt(self, value):
        try:
            if value is None:
                return value
            return int(value)
        except:
            return None

    def __generatePOSTParams(self, station):
        stationParamKey = "locs__" + str(station)
        today = rmCurrentDayTimestamp()
        ty, tm, td = rmYMDFromTimestamp(today)
        py, pm, pd = rmYMDFromTimestamp(today - 86400 * 3) #TODO: does not account for daylight savings

        POSTParams = {
            stationParamKey:"on",
            "reportType":   "daily",
            "presetRange":  3,
            "fromDate_m":   pm,
            "fromDate_d":   pd,
            "fromDate_y":   py,
            "toDate_m":     tm,
            "toDate_d":     td,
            "toDate_y":     ty,
            "vars__AirTemp15":  "on",
            "vars__TotalRad":   "on",
            "vars__ET":         "on",
            "vars__DewPoint":   "on",
            "vars__RelHumAvg":  "on",
            "vars__Rainfall":   "on",
            "vars__TotalRad":   "on",
            "vars__WindSpeed":  "on",
            "vars__WindDir":    "on",
            "vars__BP":         "on",
            "format":   ".CSV (Excel)"
        }

        return POSTParams


if __name__ == "__main__":
    p = FAWN()
    p.perform()