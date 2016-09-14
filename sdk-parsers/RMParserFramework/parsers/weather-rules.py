# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmRules import RMRules
from RMParserFramework.rmParserManager import RMParserManager
from RMNetworkFramework.API4Client.rmAPIClient import *


import json,time
import datetime, calendar
import operator


class WeatherRules(RMParser):
    parserName = "Weather Rules Parser"
    parserDescription = "RainMachine Weather Rules with WUnderground instant data. This feature is in early development " \
                        "do not enable unless you know what you are doing."
    parserForecast = True
    parserHistorical = True
    parserEnabled = False
    parserDebug = True
    parserInterval = 3600

    api = None
    #api.auth.login('admin', True) # No need to login if you connect to localhost
    # Init Rules engine
    rules = RMRules()


    params = {"apiKey" : "",
              "stationName": "",
              "_observations": {},
              "rules": """[
                {
                  "variable": "temperature",
                  "operator": ">",
                  "value": 36,
                  "action": "log",
                  "params": {"msg": "Temperature over 36 degrees"}
                }
              ]""",
              "_actions": {},
              }

    # Add actions to the parser params list
    params["_actions"] = rules.availableActions.keys()

    def isEnabledForLocation(self, timezone, lat, long):
        return False


    # Init the RainMachine REST API
    def initAPIClient(self):
        if self.api is None:
            self.api = RMAPIClient(host="127.0.0.1", port="18080")
            # Add all available API actions
            self.rules.addActions(self.api.getAllMethods())


    def perform(self):

        self.initAPIClient()

        # Build WUnderground instand data URL
        URL = self.__buildUrl()
        if URL is None:
            return

        log.info(URL)
        jsonContent = self.__getStationData(URL)
        if jsonContent is None:
            return

        log.info(jsonContent)

        observations = self.__parseStationData(jsonContent)

        #self.addValue(RMParser.dataType.TEMPERATURE, rmCurrentTimestamp(), self.observations["temperature"])

        try:
            jsonRules = json.loads(self.params["rules"])
            for rule in jsonRules:
                self.rules.addRuleSerialized(rule)
        except Exception, e:
            log.info("Error: Cannot load rules: %s", e)
            self.lastKnownError = "Error: Cannot load rules"
            return

        #self.rules.addRuleSerialized("temperature", ">", 27, "startProgram", {"id": 1})
        #self.rules.addRuleSerialized("temperature", ">", 27, "log", {"msg": "Temperature exceeded"})
        #self.rules.addRule("temperature", ">", 27, "log", "Temperature over 27 degrees")
        #self.rules.addRule("temperature", ">", 27, "addValue", RMParser.dataType.TEMPERATURE, rmCurrentTimestamp(), observations["temperature"])

        self.rules.check(observations)
        # Refresh observations in params
        self.params["_observations"] = observations
        # Refresh actions if any action was added
        self.params["_actions"] = self.rules.availableActions.keys()


    # Overwrite base method so we don't retry parser run because it returns no values
    def hasValues(self):
        return True

    def __buildUrl(self):
        apiKey =  self.params.get("apiKey", None)
        station = self.params.get("stationName", None)

        if apiKey is None or not apiKey or not isinstance(apiKey, str):
            log.error("No API Key provided")
            self.lastKnownError = "Error: No API Key provided"
            return None

        if station is None:
            log.error("No station name provided")
            self.lastKnownError = "Error: No station name provided"
            return None

        URL = "http://api.wunderground.com/api/" + str(apiKey) + "/conditions/q/pws:" + str(station) + ".json"

        return URL


    def __getStationData(self, URL):
        try:
            d = self.openURL(URL)
            jsonResponse = d.read()
            jsonContent = json.loads(jsonResponse)
            jsonContent = jsonContent["current_observation"]
        except Exception, e:
            log.error("Invalid data received %s" % e)
            self.lastKnownError = "Error: Invalid data received"
            return None

        try:
            error = jsonContent["response"]["error"]
            log.error("Error %s" % error["description"])
            self.lastKnownError = error["description"]
            return None
        except:
            pass

        return jsonContent


    def __parseStationData(self, jsonContent):
        observations = {}

        try:
            temperature = self.__toFloat(jsonContent.get("temp_c", None))
            rh = self.__toFloat(jsonContent.get("relative_humidity", None))
            wind = self.__toFloat(jsonContent.get("wind_kph", None))
            wind_gust = self.__toFloat(jsonContent.get("wind_gust_kph", None))
            pressure = self.__toFloat(jsonContent.get("pressure_mb", None))
            dew = self.__toFloat(jsonContent.get("dewpoint_c", None))
            heat = self.__toFloat(jsonContent.get("heat_index_c", None))
            rain = self.__toFloat(jsonContent.get("precip_1hr_metric", None))
            # Conversions
            if wind is not None: #kph to mps
                wind = wind / 3.6

            if pressure is not None: # mb to kpa
                pressure = pressure / 10

            observations["temperature"] = temperature
            observations["rh"] = rh
            observations["wind"] = wind
            observations["wind_gust"] = wind_gust
            observations["pressure"] = pressure
            observations["dew"] = dew
            observations["heat"] = heat
            observations["rain"] = rain

        except Exception, e:
            log.error("Can't parse data %s" % e)
            self.lastKnownError = "Error: Can't parse data"

        return observations



    def __toFloat(self, value):
        try:
            return float(value)
        except:
            return None

if __name__ == "__main__":
    p = WeatherRules()
    p.perform()