# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


opefrom RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMDataFramework.rmUserSettings import globalSettings

import json

class ForecastIO(RMParser):
    parserName = "ForecastIO Parser"
    parserDescription = "Global weather service from https://darksky.net (forecast.io)"
    parserForecast = True
    parserHistorical = False
    parserID = "forecastio"
    parserInterval = 6 * 3600
    parserEnabled = False
    parserDebug = False

    params = {"appKey": None}

    def isEnabledForLocation(self, timezone, lat, long):
        if ForecastIO.parserEnabled:
            appKey = self.params.get("appKey", None)
            return appKey is not None
        return False

    def perform(self):
        s = self.settings

        appKey = self.params.get("appKey", None)
        if appKey is None:
            self.lastKnownError = "Error: No Api Key"
            return

        URL = "https://api.darksky.net/forecast/" + str(appKey) + "/" + str(s.location.latitude) + "," + str(s.location.longitude)

        # URLParams = \
        #     [
        #         ("units", "si"),
        #         ("exclude", "currently,minutely,alerts,flags"),
        #         ("extend", "hourly")
        #     ]

        URLParams = \
            [
                ("units", "si"),
                ("exclude", "currently,minutely,alerts,flags, hourly")
            ]

        try:
            d = self.openURL(URL, URLParams)
            if d is None:
                return

            forecast = json.loads(d.read())
            self.__getDailyData(forecast)

        except Exception, e:
            log.error("*** Error running darksky.net parser")
            log.exception(e)

        log.debug("Finished running darksky.net parser")

    def __getDailyData(self, forecast):
        dayTimestamp = rmCurrentDayTimestamp()
        maxDayTimestamp = dayTimestamp + globalSettings.parserDataSizeInDays * 86400

        daily = []
        try:
            daily = forecast["daily"]["data"]
        except Exception, e:
            log.error("*** No daily information found in response!")
            self.lastKnownError = "Warning: No daily information"
            log.exception(e)

        for entry in daily:
            timestamp = entry.get("time")
            if timestamp is None:
                continue

            timestamp = int(timestamp)

            if timestamp < maxDayTimestamp:
                self.addValue(RMParser.dataType.QPF, timestamp, entry.get("precipIntensity") * 24)
                self.addValue(RMParser.dataType.RH, timestamp, self.convertToPercent(entry.get("humidity")))
                self.addValue(RMParser.dataType.WIND, timestamp, entry.get("windSpeed"))
                self.addValue(RMParser.dataType.POP, timestamp, self.convertToPercent(entry.get("precipProbability")))
                self.addValue(RMParser.dataType.DEWPOINT, timestamp, entry.get("dewPoint"))
                self.addValue(RMParser.dataType.MINTEMP, timestamp, entry.get("temperatureMin"))
                self.addValue(RMParser.dataType.MAXTEMP, timestamp, entry.get("temperatureMax"))
                self.addValue(RMParser.dataType.CONDITION, timestamp, self.conditionConvert(entry.get("icon")))

        if self.parserDebug:
            log.debug(self.result)

    def __getHourlyData(self, forecast):

        dayTimestamp = rmCurrentDayTimestamp()
        maxDayTimestamp = dayTimestamp + globalSettings.parserDataSizeInDays * 86400

        hourly = []
        try:
            hourly = forecast["hourly"]["data"]
        except Exception, e:
            log.error("*** No hourly information found in response!")
            log.exception(e)
            self.lastKnownError = "Warning: No hourly information"

        for entry in hourly:
            timestamp = entry.get("time")
            if timestamp is None:
                continue

            timestamp = int(timestamp)

            if timestamp < maxDayTimestamp:
                self.addValue(RMParser.dataType.TEMPERATURE, timestamp, entry.get("temperature"))
                self.addValue(RMParser.dataType.QPF, timestamp, entry.get("precipIntensity"))
                self.addValue(RMParser.dataType.RH, timestamp, self.convertToPercent(entry.get("humidity")))
                self.addValue(RMParser.dataType.WIND, timestamp, entry.get("windSpeed"))
                self.addValue(RMParser.dataType.POP, timestamp, self.convertToPercent(entry.get("precipProbability")))
                self.addValue(RMParser.dataType.DEWPOINT, timestamp, entry.get("dewPoint"))

                # Forecast.io gives pressure in milibars but formula expects in kilopascals 1 milibar = 0.1 kPa
                try:
                    pressure = entry.get("pressure")
                    pressure = pressure / 10
                except:
                    pressure = None

                self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)

    def conditionConvert(self, conditionStr):
        if 'clear-day' in conditionStr:
            return RMParser.conditionType.Fair
        elif 'clear-night' in conditionStr:
            return RMParser.conditionType.Fair
        elif 'rain' in conditionStr:
            return RMParser.conditionType.HeavyRain
        elif 'snow' in conditionStr:
            return RMParser.conditionType.Snow
        elif 'sleet' in conditionStr:
            return RMParser.conditionType.RainSnow
        elif 'wind' in conditionStr:
            return RMParser.conditionType.Windy
        elif 'fog' in conditionStr:
            return RMParser.conditionType.Fog
        elif 'cloudy' in conditionStr:
            return RMParser.conditionType.FewClouds
        elif 'partly-cloudy-day' in conditionStr:
            return RMParser.conditionType.PartlyCloudy
        elif 'partly-cloudy-night' in conditionStr:
            return RMParser.conditionType.PartlyCloudy
        elif 'hail' in conditionStr:
            return RMParser.conditionType.RainIce
        elif 'thunderstorm' in conditionStr:
            return RMParser.conditionType.Thunderstorm
        elif 'tornado' in conditionStr:
            return RMParser.conditionType.FunnelCloud
        else:
            return RMParser.conditionType.Unknown

    def convertToPercent(self, f):
        try:
                return f * 100
        except:
                return None