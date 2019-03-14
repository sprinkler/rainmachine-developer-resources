# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>

# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMDataFramework.rmUserSettings import globalSettings

import json

class OpenWeatherMap(RMParser):
    parserName = "OpenWeatherMap Parser"
    parserDescription = "Global weather service from https://openweathermap.org/"
    parserForecast = True
    parserHistorical = False
    parserID = "openweathermap"
    parserInterval = 6 * 3600
    parserEnabled = True
    parserDebug = False

    params = {"apiKey": None}


    def isEnabledForLocation(self, timezone, lat, long):
        if OpenWeatherMap.parserEnabled:
            apiKey = self.params.get("apiKey", None)
            return apiKey is not None
        return False

    def perform(self):
        s = self.settings

        apiKey = self.params.get("apiKey", None)
        if apiKey is None:
            self.lastKnownError = "Error: No API Key. Please register for a free account on https://openweathermap.org/."
            return

        URL = "https://api.openweathermap.org/data/2.5/forecast"

        URLParams = [
            ("appid", str(apiKey)),
            ("lat", str(s.location.latitude)),
            ("lon", str(s.location.longitude)),
            ("units", "metric"),
        ]

        forecast = None
        try:

            d = self.openURL(URL, URLParams)
            if d is None:
                return

            forecast = json.loads(d.read())

            if self.parserDebug:
                with open("dump.json", "w") as f:
                    json.dump(forecast, f)
                log.info(forecast)

            self.__getForecastData(forecast)

        except Exception, e:
            log.error("*** Error running OpenWeatherMap parser")
            log.exception(e)

        log.debug("Finished running OpenWeatherMap parser")

    def __getForecastData(self, forecast):
        dayTimestamp = rmCurrentDayTimestamp()

        if "list" not in forecast:
            self.lastKnownError = "Error: Missing data cannot parse response JSON."
            log.info(self.lastKnownError)
            return

        for entry in forecast["list"]:
            timestamp = entry["dt"]

            if self.parserDebug:
                log.info("Date: %s" % rmTimestampToDateAsString(timestamp))

            maxtemp = None
            mintemp = None
            temp = None
            humidity = None
            pressure = None

            if "main" in entry:
                maxtemp = entry["main"].get("temp_max")
                mintemp = entry["main"].get("temp_min")
                temp = entry["main"].get("temp")
                humidity = entry["main"].get("humidity")
                pressure = entry["main"].get("grnd_level")
                try:
                    pressure = pressure / 10 # hPa to kPa
                except:
                    pressure = None

            self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp)
            self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp)
            self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temp)
            self.addValue(RMParser.dataType.RH, timestamp, humidity)
            self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)

            qpf = None
            if "rain" in entry:
                qpf = entry["rain"].get("3h")

            self.addValue(RMParser.dataType.QPF, timestamp, qpf)

            wind = None
            if "wind" in entry:
                wind = entry["wind"].get("speed")

            self.addValue(RMParser.dataType.WIND, timestamp, wind)

            icon = None
            if entry["weather"][0]:
                icon = self.conditionConvert(entry["weather"][0].get("id"))

            self.addValue(RMParser.dataType.CONDITION, timestamp, icon)

        if self.parserDebug:
            log.debug(self.result)

    # https://openweathermap.org/weather-conditions
    def conditionConvert(self, id):
        if id is None:
            return RMParser.conditionType.Unknown

        if 200 <= id <= 232:
            return RMParser.conditionType.Thunderstorm

        if 300 <= id <= 321 or id == 520 or id == 521:
            return RMParser.conditionType.RainShowers

        if id == 500 or id == 501:
            return RMParser.conditionType.LightRain

        if id >= 502 and id <= 504:
            return RMParser.conditionType.HeavyRain

        if id == 511:
            return RMParser.conditionType.FreezingRain

        if (600 <= id <= 602) or (620 <= id <= 622):
            return RMParser.conditionType.Snow

        if id == 611 or id == 612:
            return RMParser.conditionType.RainIce

        if id == 615 or id == 616:
            return RMParser.conditionType.RainSnow

        if id == 700 or id == 741:
            return RMParser.conditionType.Fog

        if id == 711:
            return RMParser.conditionType.Smoke

        if id == 721:
            return RMParser.conditionType.Haze

        if id == 731 or id == 751 or id == 761 or id == 762:
            return RMParser.conditionType.Dust

        if id == 771 or id == 905:
            return RMParser.conditionType.Windy

        if id == 781 or id == 900 or id == 901 or id == 902:
            return RMParser.conditionType.FunnelCloud

        if id == 800:
            return  RMParser.conditionType.Fair

        if id == 801:
            return RMParser.conditionType.FewClouds

        if id == 802:
            return RMParser.conditionType.PartlyCloudy

        if id == 803:
            return RMParser.conditionType.MostlyCloudy

        if id == 804:
            return RMParser.conditionType.Overcast

        if id == 903:
            return RMParser.conditionType.Cold

        if id == 904:
            return RMParser.conditionType.Hot

        if id == 906:
            return RMParser.conditionType.IcePellets

        return RMParser.conditionType.Unknown


if __name__ == "__main__":
    parser = OpenWeatherMap()
    parser.perform()
