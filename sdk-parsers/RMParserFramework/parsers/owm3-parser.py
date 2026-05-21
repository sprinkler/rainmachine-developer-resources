# Copyright (c) 2024 RainMachine, Green Electronics LLC
# All rights reserved.

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *

import json


class OpenWeatherMapOneCall(RMParser):
    parserName        = "OpenWeatherMap - One Call 3.0"
    parserDescription = "Global weather service from https://openweathermap.org/"
    parserForecast    = True
    parserHistorical  = False
    parserID          = "openweathermap3"
    parserInterval    = 1 * 3600
    parserEnabled     = True
    parserDebug       = False

    params = {"apiKey": None}

    def isEnabledForLocation(self, timezone, lat, long):
        if OpenWeatherMapOneCall.parserEnabled:
            return self.params.get("apiKey") is not None
        return False

    def perform(self):
        s = self.settings

        apiKey = self.params.get("apiKey", None)
        if apiKey is None:
            self.lastKnownError = "Error: No API Key. Activate 'One Call by Call' subscription at openweathermap.org and enter your key."
            return

        URL = "https://api.openweathermap.org/data/3.0/onecall"
        URLParams = [
            ("lat",     str(s.location.latitude)),
            ("lon",     str(s.location.longitude)),
            ("appid",   str(apiKey)),
            ("units",   "metric"),
            ("exclude", "current,minutely,alerts"),
        ]

        try:
            d = self.openURL(URL, URLParams)
            if d is None:
                return

            data = json.loads(d.read())

            if self.parserDebug:
                with open("owm3-dump.json", "w") as f:
                    json.dump(data, f)
                log.info(data)

            if "hourly" not in data and "daily" not in data:
                self.lastKnownError = "Error: Missing hourly and daily data in response."
                log.error(self.lastKnownError)
                return

            self.__parseHourly(data.get("hourly", []))
            self.__parseDaily(data.get("daily", []))

        except Exception, e:
            log.error("*** Error running OpenWeatherMap One Call 3.0 parser")
            log.exception(e)

        log.debug("Finished running OpenWeatherMap One Call 3.0 parser")

    def __parseHourly(self, hourly):
        for entry in hourly:
            timestamp = entry["dt"]

            temp     = entry.get("temp")
            humidity = entry.get("humidity")
            pressure = entry.get("pressure")
            wind     = entry.get("wind_speed")
            dewpoint = entry.get("dew_point")
            skycover = entry.get("clouds")
            pop      = entry.get("pop")

            rain = entry.get("rain") or {}
            qpf  = rain.get("1h", None)

            weather   = entry.get("weather") or []
            condition = self.conditionConvert(weather[0].get("id")) if weather else RMParser.conditionType.Unknown

            try:
                pressure = pressure / 10.0  # hPa -> kPa
            except:
                pressure = None

            pop_pct = pop * 100 if pop is not None else None

            if self.parserDebug:
                log.info("Hourly %s: temp=%s rh=%s wind=%s dewpoint=%s qpf=%s pop=%s sky=%s" % (
                    rmTimestampToDateAsString(timestamp), temp, humidity, wind, dewpoint, qpf, pop_pct, skycover))

            self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temp)
            self.addValue(RMParser.dataType.RH,          timestamp, humidity)
            self.addValue(RMParser.dataType.PRESSURE,    timestamp, pressure)
            self.addValue(RMParser.dataType.WIND,        timestamp, wind)
            self.addValue(RMParser.dataType.DEWPOINT,    timestamp, dewpoint)
            self.addValue(RMParser.dataType.QPF,         timestamp, qpf)
            self.addValue(RMParser.dataType.CONDITION,   timestamp, condition)
            self.addValue(RMParser.dataType.POP,         timestamp, pop_pct)
            self.addValue(RMParser.dataType.SKYCOVER,    timestamp, skycover)

    def __parseDaily(self, daily):
        for entry in daily:
            timestamp = entry["dt"]

            temp    = entry.get("temp") or {}
            mintemp = temp.get("min", None)
            maxtemp = temp.get("max", None)

            humidity = entry.get("humidity")
            wind     = entry.get("wind_speed")
            dewpoint = entry.get("dew_point")
            pressure = entry.get("pressure")
            skycover = entry.get("clouds")
            qpf      = entry.get("rain")  # plain float mm/day, not a dict
            pop      = entry.get("pop")

            weather   = entry.get("weather") or []
            condition = self.conditionConvert(weather[0].get("id")) if weather else RMParser.conditionType.Unknown

            try:
                pressure = pressure / 10.0  # hPa -> kPa
            except:
                pressure = None

            pop_pct = pop * 100 if pop is not None else None

            if self.parserDebug:
                log.info("Daily %s: min=%s max=%s rh=%s wind=%s dewpoint=%s qpf=%s pop=%s sky=%s" % (
                    rmTimestampToDateAsString(timestamp), mintemp, maxtemp, humidity, wind, dewpoint, qpf, pop_pct, skycover))

            self.addValue(RMParser.dataType.MINTEMP,   timestamp, mintemp)
            self.addValue(RMParser.dataType.MAXTEMP,   timestamp, maxtemp)
            self.addValue(RMParser.dataType.RH,        timestamp, humidity)
            self.addValue(RMParser.dataType.WIND,      timestamp, wind)
            self.addValue(RMParser.dataType.DEWPOINT,  timestamp, dewpoint)
            self.addValue(RMParser.dataType.PRESSURE,  timestamp, pressure)
            self.addValue(RMParser.dataType.CONDITION, timestamp, condition)
            self.addValue(RMParser.dataType.SKYCOVER,  timestamp, skycover)
            self.addValue(RMParser.dataType.QPF,       timestamp, qpf)
            self.addValue(RMParser.dataType.POP,       timestamp, pop_pct)

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
            return RMParser.conditionType.Fair

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
    import os

    class _Location(object):
        latitude  = float(os.environ.get("RM_LAT",       "44.43"))
        longitude = float(os.environ.get("RM_LON",       "26.10"))
        elevation = float(os.environ.get("RM_ELEVATION",  "80.0"))

    class _Settings(object):
        location = _Location()

    p = OpenWeatherMapOneCall()
    p.parserDebug = True
    p.settings = _Settings()
    p.params["apiKey"] = os.environ.get("OWM_API_KEY", "")
    p.perform()

    print "\n--- OWM3 result: %d entries ---" % len(p.result)
    for ts in sorted(p.result):
        print p.result[ts]
