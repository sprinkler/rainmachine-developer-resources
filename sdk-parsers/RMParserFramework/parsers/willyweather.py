# Copyright (c) 2018 Richard Mann
# All rights reserved.
# Author: Richard Mann <mann_rj@hotmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
# -----------------------------------------------------------------------
#
# WillyWeather is an Australian weather service and commercial API.
# Users must pay a per-transaction fee to access API data once 5000
# calls are reached.
#
# You must first obtain an API key from
# https://www.willyweather.com.au/info/api.html
#
# Select "Single Location" from the options.
# Select "Observational" and "Forecasts" from the sub-menu under Weather.
# This should give a $0.09 cost per 1000 requests.
#
# Enter your API key in the UI and Save, then Refresh.
# In the UI, a list of nearby stations should appear, based on your
# RainMachine latitude and longitude settings.
#
# Unticking stationLookUp will save 2 API calls once you are configured
#
# Enter the desired Station ID in the box and save the settings.

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMDataFramework.rmUserSettings import globalSettings

import json

class WillyWeather(RMParser):
    parserName = "Australia WillyWeather"
    parserDescription = "Retrieve data from WillyWeather Australian weather service"
    parserForecast = True
    parserHistorical = True
    parserID = "willyweather"
    parserInterval = 6 * 3600
    parserEnabled = True
    parserDebug = False

    params = {
              "apiKey": None,
              "stationID": None,
              "stationLookUp": False,
              "_nearbyStationsIDList": []
              }

    defaultParams = {
              "apiKey": None,
              "stationID": 13960,
              "stationLookUp": True,
              "_nearbyStationsIDList": []
              }

    forecast = None

    def isEnabledForLocation(self, timezone, lat, long):
        return WillyWeather.parserEnabled

    def perform(self):
        self.apiKey = self.params.get("apiKey", None)
        self.stationID = self.params.get("stationID", None)
        if self.apiKey is None or not self.apiKey or not isinstance(self.apiKey, str):
            self.lastKnownError = "Error: No API Key. Please register an account at https://www.willyweather.com.au/info/api.html"
            return

        self.params["_nearbyStationsIDList"] = []
        self.noDays = 7

        if self.params.get("stationLookUp"):
            s = self.settings
            llat = s.location.latitude
            llon = s.location.longitude

            searchURL = "https://api.willyweather.com.au/v2/" + self.apiKey + "/search.json"
            searchURLParams = [
                ("lat", llat),
                ("lng", llon),
                ("units", "distance:km")
            ]

            try:
                d = self.openURL(searchURL, searchURLParams)
                if d is None:
                    return

                search = json.loads(d.read())

                if self.parserDebug:
                    log.info(search)

                self.getNearbyStations(search)

            except Exception, e:
                log.error("*** Error finding nearby stations")
                log.exception(e)

        if self.stationID is None:
            self.lastKnownError = "Error: No Station ID entered."
            return

        URL = "https://api.willyweather.com.au/v2/" + self.apiKey + "/locations/" + str(self.stationID) + "/weather.json"

        URLParams = [
            ("observational", "true"),
            ("forecasts", "weather,temperature,rainfall,wind"),
            ("days", self.noDays),
            {"units", "speed:m/s"}
        ]

        try:
            d = self.openURL(URL, URLParams)
            if d is None:
                return

            forecast = json.loads(d.read())

            if self.parserDebug:
                log.info(forecast)

            self.__getForecastData(forecast)


        except Exception, e:
            log.error("*** Error running WillyWeather parser")
            log.exception(e)

        log.debug("Finished running WillyWeather parser")

    def __getForecastData(self, forecast):
        datetime = forecast["observational"].get("issueDateTime")
        obstimestamp = rmTimestampFromDateAsString(datetime, '%Y-%m-%d %H:%M:%S')

        obsstartofday = rmGetStartOfDayUtc(obstimestamp)
        obssoddatetime = rmTimestampToUtcDateAsString(obsstartofday)

        orain = forecast["observational"]["observations"]["rainfall"].get("todayAmount")

        if self.parserDebug:
            log.info("Obs datetime:        %s" % datetime)
            log.info("Obs Start of Day:    %s" % obssoddatetime)
            log.info("Obs rain:            %s mm today" % orain)

        self.addValue(RMParser.dataType.RAIN, obsstartofday, orain)

        day = 0

        while day < self.noDays:
            datetime = forecast["forecasts"]["weather"]["days"][day]["entries"][0].get("dateTime")
            timestamp = rmTimestampFromDateAsString(datetime, '%Y-%m-%d %H:%M:%S')

            if self.parserDebug:
                log.info("Forecast Date: %s" % rmTimestampToDateAsString(timestamp))

            maxtemp = forecast["forecasts"]["weather"]["days"][day]["entries"][0].get("max")
            mintemp = forecast["forecasts"]["weather"]["days"][day]["entries"][0].get("min")
            precis  = self.conditionConvert(forecast["forecasts"]["weather"]["days"][day]["entries"][0].get("precisCode"))

            self.addValue(RMParser.dataType.CONDITION, timestamp, precis)

            for entry in forecast["forecasts"]["temperature"]["days"][day]["entries"]:
                datetime = entry.get("dateTime")
                timestamp = rmTimestampFromDateAsString(datetime, '%Y-%m-%d %H:%M:%S')

                temperature = entry.get("temperature")

                self.addValue(RMParser.dataType.TEMPERATURE, timestamp, round(temperature, 2))
                self.addValue(RMParser.dataType.MINTEMP, timestamp, round(mintemp, 2))
                self.addValue(RMParser.dataType.MAXTEMP, timestamp, round(maxtemp, 2))

            for entry in forecast["forecasts"]["wind"]["days"][day]["entries"]:
                datetime = entry.get("dateTime")
                timestamp = rmTimestampFromDateAsString(datetime, '%Y-%m-%d %H:%M:%S')

                wind = entry.get("speed")

                self.addValue(RMParser.dataType.WIND, timestamp, round(wind, 2))

            for entry in forecast["forecasts"]["rainfall"]["days"][day]["entries"]:
                datetime = entry.get("dateTime")
                timestamp = rmTimestampFromDateAsString(datetime, '%Y-%m-%d %H:%M:%S')

                rainfallmin = entry.get("startRange")
                rainfallmax = entry.get("endRange")
                rainfallprob = entry.get("probability")
                rainfallavg = (self.__toFloat(rainfallmin) + self.__toFloat(rainfallmax))/2

                self.addValue(RMParser.dataType.QPF, timestamp, rainfallavg)
                self.addValue(RMParser.dataType.POP, timestamp, rainfallprob)

            day += 1

        if self.parserDebug:
            log.debug(self.result)

    def getNearbyStations(self, jsonData):
        try:
            nearestStation = jsonData["location"].get("id")
        except:
            log.warning("No closest station found!")
            self.lastKnownError = "Warning: No closest station found!"
            return

        closestURL = "https://api.willyweather.com.au/v2/" + self.apiKey + "/search/closest.json"
        closestURLParams = [
            ("id", nearestStation),
            ("weatherTypes", "general"),
            ("units", "distance:km")
        ]

        try:
            d = self.openURL(closestURL, closestURLParams)
            if d is None:
                return

            closest = json.loads(d.read())

            if self.parserDebug:
                log.info(closest)

            for i in closest["general"]:
                id = i["id"]
                name = i["name"]
                region = i["region"]
                postcode = i["postcode"]
                distance = i["distance"]

                infoStr = "Station ID = " + str(id) + " (" + name + ", " + region + ", " + str(postcode) + ", " + str(distance) + " kms away)"

                self.params["_nearbyStationsIDList"].append(infoStr)
			
            if self.parserDebug:
                log.debug(self.params["_nearbyStationsIDList"])

        except Exception, e:
            log.error("*** Error running WillyWeather parser")
            log.exception(e)

    def __toFloat(self, value):
        if value is None:
            return 0
        return float(value)

    def conditionConvert(self, precisCode):
        if precisCode is None:
            return RMParser.conditionType.Unknown

        if precisCode == "cloudy":
            return RMParser.conditionType.MostlyCloudy

        if precisCode == "fine":
            return  RMParser.conditionType.Fair

        if precisCode == "mostly-fine":
            return RMParser.conditionType.FewClouds

        if precisCode == "partly-cloudy" or precisCode == "mostly-cloudy" or precisCode == "high-cloud":
            return RMParser.conditionType.PartlyCloudy

        if precisCode == "overcast":
            return RMParser.conditionType.Overcast

        if precisCode == "fog":
            return RMParser.conditionType.Fog

        if precisCode == "hail":
            return RMParser.conditionType.IcePellets

        if precisCode == "snow-and-rain":
            return RMParser.conditionType.RainSnowFix

        if precisCode == "showers-rain":
            return RMParser.conditionType.RainShowers

        if precisCode == "thunderstorm" or precisCode == "chance-thunderstorm-showers":
            return RMParser.conditionType.Thunderstorm

        if "snow" in precisCode:
            return RMParser.conditionType.Snow

        if precisCode == "wind":
            return RMParser.conditionType.Windy

        if precisCode == "chance-shower-fine" or precisCode == "shower-or-two" or precisCode == "chance-shower-cloud":
            return RMParser.conditionType.ShowersInVicinity

        if precisCode == "chance-thunderstorm-cloud" or precisCode == "chance-thunderstorm-fine":
            return RMParser.conditionType.ThunderstormInVicinity

        if precisCode == "drizzle" or precisCode == "few-showers":
            return RMParser.conditionType.LightRain

        if precisCode == "heavy-showers-rain":
            return RMParser.conditionType.HeavyRain

        if precisCode == "dust":
            return RMParser.conditionType.Dust

        if precisCode == "frost":
            return RMParser.conditionType.Cold

        return RMParser.conditionType.Unknown


if __name__ == "__main__":
    parser = WillyWeather()
    parser.perform()
