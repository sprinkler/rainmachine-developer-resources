# Copyright (c) 2014-2019 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>

# This weather parser is an alternative version to the fawn-parser.py because FAWN API data feeds no longer output ET


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmUtils import *
from RMDataFramework.rmWeatherData import RMWeatherConditions

import datetime, time, urllib, urllib2
import csv

class FAWNReport(RMParser):
    parserName = "FAWN Report Parser"
    parserDescription = "Florida Automated Weather Network observations alternative mode"
    parserForecast = False
    parserHistorical = True
    parserEnabled = False
    parserDebug = True
    parserInterval = 6 * 3600
    params = { "station": 480 }

    def isEnabledForLocation(self, timezone, lat, long):
        if FAWNReport.parserEnabled and timezone:
            return timezone.startswith("US") or timezone.startswith("America")
        return False

    def perform(self):
        s = self.settings

        now = time.time()
        URLReport = "https://fawn.ifas.ufl.edu/data/reports/?res" #+ str(now)
        station = self.params.get("station", None)

        if station is None:
            self.lastKnownError = "No station number configured."
            log.error(self.lastKnownError)
            return

        POSTParams = self.__generatePOSTParams(station)

        #-----------------------------------------------------------------------------------------------
        #
        # Get daily data.
        #
        try:
            POSTParams = urllib.urlencode(POSTParams)
            req = urllib2.Request(URLReport, data=POSTParams)
            response = urllib2.urlopen(req)
            data = response.read()
        except Exception, e:
            self.lastKnownError = "Cannot download data"
            log.error(self.lastKnownError)
            log.error(e)
            return

        if data is None:
            return

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


    def __toFloat(self, value):
        try:
            if value is None:
                return value
            return float(value)
        except:
            return None

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
    p = FAWNReport()
    p.perform()