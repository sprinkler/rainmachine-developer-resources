# -*- coding: utf-8 -*-

# AccuWeather Network parser for RainMachine smart sprinkler controller
#
# Feed forecast weather data from www.accuweather.com into your RainMachine
# Requires an API key, zip code / location key (acquired based on zip code)
#
# Author: gitzone83 (https://github.com/gitzone83)
#
# 20210804:
#   - first version using data from AccuWeather
#
# LICENSE: GNU General Public License v3.0
# GitHub: https://github.com/gitzone83/accuweather.rainmachine
#

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions
import json
import urllib, urllib2, ssl

class AccuWeatherParser(RMParser):
    parserName = "AccuWeather Network Weather Information Parser"
    parserDescription = "Weather data from www.accuweather.com"
    parserForecast = True
    parserHistorical = False
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600  # every 6 hours
    parserHasData = False

    parserRequestHeaders = {"User-Agent": "accuweather-parser/1.0"}

    params = {"ApiKey": None, "ZipCode": None, "LocationKey": None}

    def perform(self):

        # acquire location key if not provided explicitly, according to AccuWeather API, it will consume one API call to perform the lookup
        if 'None' in str(self.params["LocationKey"]) and not 'None' in str(self.params["ZipCode"]):
            self.params["LocationKey"] = self.obtainLocationKey()

        varApiUrl = 'http://dataservice.accuweather.com/forecasts/v1/daily/5day/' + str(self.params["LocationKey"])
        varApiParameterList = [("apikey", str(self.params["ApiKey"])), ("details", "true"), ("metric", "true")]

        log.info('Getting data from {0}'.format(str(varApiUrl)))

        query_string = urllib.urlencode(varApiParameterList)
        varApiUrlQuery = "?".join([varApiUrl, query_string])

        print(varApiUrlQuery)

        try:
            varApiRequest = urllib2.Request(url=varApiUrlQuery, headers=self.parserRequestHeaders)
            varApiData = urllib2.urlopen(url=varApiRequest, timeout=60)
            log.debug("Connected to %s" % varApiUrlQuery)
        except Exception as e:
            self.lastKnownError = "Connection Error"
            log.error("Error while connecting to %s, error: %s" % (varApiUrl, e))
            return

        varApiHttpStatus = varApiData.getcode()
        log.debug("varApiHttpStatus = %s" % (varApiHttpStatus))
        if varApiHttpStatus != 200:
            self.lastKnownError = "HTTP Error " + varApiHttpStatus
            log.error("URL %s failed with code %s" % (varApiUrl, varApiHttpStatus))
            return

        varApiDataReceived = json.loads(varApiData.read())
        varApiDataReceivedDaily = varApiDataReceived["DailyForecasts"]

        # examine each daily entry
        for varApiDataEntry in varApiDataReceivedDaily:

            varEntryTime = varApiDataEntry["EpochDate"]

            if 'Value' in varApiDataEntry["Temperature"]["Maximum"]:
                varEntryTemp = varApiDataEntry["Temperature"]["Maximum"]["Value"]
                self.addValue(RMParser.dataType.MAXTEMP, varEntryTime, varEntryTemp, False)
                log.debug("TEMPERATURE MAX = %s" % (varEntryTemp))
                self.parserHasData = True

            if 'Value' in varApiDataEntry["Temperature"]["Minimum"]:
                varEntryTemp = varApiDataEntry["Temperature"]["Minimum"]["Value"]
                self.addValue(RMParser.dataType.MINTEMP, varEntryTime, varEntryTemp, False)
                log.debug("TEMPERATURE MIN = %s" % (varEntryTemp))
                self.parserHasData = True

            if 'Value' in varApiDataEntry["Day"]["Wind"]["Speed"]:
                varEntryWindSpeed = varApiDataEntry["Day"]["Wind"]["Speed"]["Value"] * 0.27777778 # to meters/sec
                self.addValue(RMParser.dataType.WIND, varEntryTime, varEntryWindSpeed, False)
                log.debug("WIND = %s" % (varEntryWindSpeed))
                self.parserHasData = True

            if 'Value' in varApiDataEntry["Day"]["SolarIrradiance"] and 'Value' in varApiDataEntry["Night"]["SolarIrradiance"]:
                varEntrySolarIrradiance = self.convertRadiationFromWattsToMegaJoules(varApiDataEntry["Day"]["SolarIrradiance"]["Value"] + varApiDataEntry["Night"]["SolarIrradiance"]["Value"])
                self.addValue(RMParser.dataType.SOLARRADIATION, varEntryTime, varEntrySolarIrradiance, False)
                log.debug("SOLARRADIATION = %s" % (varEntrySolarIrradiance))
                self.parserHasData = True

            if 'Value' in varApiDataEntry["Day"]["Rain"] and 'Value' in varApiDataEntry["Night"]["Rain"]:
                varEntryRain = varApiDataEntry["Day"]["Rain"]["Value"] + varApiDataEntry["Night"]["Rain"]["Value"]
                self.addValue(RMParser.dataType.QPF, varEntryTime, varEntryRain, False)
                log.debug("RAIN = %s" % (varEntryRain))
                self.parserHasData = True

            if 'Value' in varApiDataEntry["Day"]["Evapotranspiration"] and 'Value' in varApiDataEntry["Night"]["Evapotranspiration"]:
                varEntryEvapotranspiration = varApiDataEntry["Day"]["Evapotranspiration"]["Value"] + varApiDataEntry["Night"]["Evapotranspiration"]["Value"]
                self.addValue(RMParser.dataType.ET0, varEntryTime, varEntryEvapotranspiration, False)
                log.debug("ET0 = %s" % (varEntryEvapotranspiration))
                self.parserHasData = True

            if 'Icon' in varApiDataEntry["Day"]:
                varCondition = self.convertIconToWeatherCondition(int(varApiDataEntry["Day"]["Icon"]))
                self.addValue(RMParser.dataType.CONDITION, varEntryTime, varCondition, False)
                enum_names = {value: name for name, value in vars(RMWeatherConditions).items()}
                log.debug("CONDITION = %s" % (enum_names[varCondition]))
                self.parserHasData = True

        if self.parserHasData:
            log.info("Successful update from AccuWeather for location %s" % (str(self.params["LocationKey"])))
        else:
            self.lastKnownError = "No Data From AccuWeather"
            log.error("Connected, but no data returned from AccuWeather for location %s" % (str(self.params["LocationKey"])))

    # Function to acquire location key if not provided explicitly, according to AccuWeather API, it will consume one API call to perform the lookup
    def obtainLocationKey(self):

        varApiUrl = 'http://dataservice.accuweather.com/locations/v1/postalcodes/search'
        varApiParameterList = [("apikey", str(self.params["ApiKey"])), ("q", str(self.params["ZipCode"])), ("details", "true")]

        log.info('Getting data from {0}'.format(str(varApiUrl)))

        query_string = urllib.urlencode(varApiParameterList)
        varApiUrlQuery = "?".join([varApiUrl, query_string])

        try:
            varApiRequest = urllib2.Request(url=varApiUrlQuery, headers=self.parserRequestHeaders)
            varApiData = urllib2.urlopen(url=varApiRequest, timeout=60)
            log.debug("Connected to %s" % varApiUrlQuery)
        except Exception, e:
            self.lastKnownError = "Connection Error"
            log.error("Error while connecting to %s, error: %s" % (varApiUrl, e))
            return

        varApiHttpStatus = varApiData.getcode()
        log.debug("varApiHttpStatus = %s" % (varApiHttpStatus))
        if varApiHttpStatus != 200:
            self.lastKnownError = "HTTP Error " + varApiHttpStatus
            log.error("URL %s failed with code %s" % (varApiUrl, varApiHttpStatus))
            return

        varApiDataReceived = json.loads(varApiData.read())

        print(varApiDataReceived[0]["Key"])

        if 'Key' in varApiDataReceived[0]:
            return str(varApiDataReceived[0]["Key"])
        else:
            return None

    # Function to convert radiation to MJ/day
    def convertRadiationFromWattsToMegaJoules(self, radiation):
        try:
            radiation = float(radiation)
            return radiation * 0.0864
        except:
            pass
        return None

    def convertIconToWeatherCondition(self, icon):
        if icon == 1:
            return RMParser.conditionType.Fair
        elif icon >= 2 and icon <= 4:
            return RMParser.conditionType.FewClouds
        elif icon >= 5 and icon <= 6:
            return RMParser.conditionType.MostlyCloudy
        elif icon >= 7 and icon <= 8:
            return RMParser.conditionType.Overcast
        elif icon == 11:
            return RMParser.conditionType.Fog
        elif icon >= 12 and icon <= 14:
            return RMParser.conditionType.RainShowers
        elif icon == 15:
            return RMParser.conditionType.Thunderstorm
        elif icon >= 16 and icon <= 17:
            return RMParser.conditionType.ThunderstormInVicinity
        elif icon == 18:
            return RMParser.conditionType.LightRain
        elif icon >= 22 and icon <= 23:
            return RMParser.conditionType.Snow
        elif icon == 29:
            return RMParser.conditionType.RainSnow
        elif icon == 35:
            return RMParser.conditionType.PartlyCloudy
        return RMParser.conditionType.Unknown;
