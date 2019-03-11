# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

from RMDataFramework.rmWeatherData import RMWeatherDataType
from RMUtilsFramework.rmLogging import log

# This is for planet Earth: https://en.wikipedia.org/wiki/List_of_weather_records
class RMWeatherDataLimits:
    def __init__(self):
        self.limits = {
            RMWeatherDataType.TEMPERATURE:      {"min": -60, "max": 60,     "units": "C"},
            RMWeatherDataType.MINTEMP:          {"min": -60, "max": 60,     "units": "C"},
            RMWeatherDataType.MAXTEMP:          {"min": -60, "max": 60,     "units": "C"},
            RMWeatherDataType.RH:               {"min": 0, "max": 1,        "units": "percent"},
            RMWeatherDataType.WIND:             {"min": 0, "max": 55.55,    "units": "m/s"},  # 200km/h
            RMWeatherDataType.SOLARRADIATION:   {"min": 0, "max": None,     "units": "Mega Joules/square meter per hour"},
            RMWeatherDataType.SKYCOVER:         {"min": 0, "max": 1,        "units": "percent"},
            RMWeatherDataType.ET0:              {"min": 0, "max": 100,       "units": "mm"},
            RMWeatherDataType.QPF:              {"min": 0, "max": 125,       "units": "mm"},
            RMWeatherDataType.RAIN:             {"min": 0, "max": 125,       "units": "mm"},
            RMWeatherDataType.PRESSURE:         {"min": 50, "max": 120,     "units": "kpa"},
        }

    def sanitize(self, key, value):
        interval = self.limits.get(key, None)
        if interval is None:
            log.info("%s key not found in our limits definitions" % key)
            return value

        min = interval["min"]
        max = interval["max"]
        if min is not None and value < min:
            log.error("%s value %s less than limits minimum of %s" % (key, value, interval["min"]))
            return None

        if max is not None and value > max:
            log.error("%s value %s more than limits maximum of %s" % (key, value, interval["max"]))
            return None

        return value


if __name__ == "__main__":
    l = RMWeatherDataLimits()
    for value in [-55.2, 0.8884, 100.1]:
        log.info("TEMPERATURE Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.TEMPERATURE, value)))
        log.info("MINTEMP     Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.MINTEMP, value)))
        log.info("MAXTEMP     Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.MAXTEMP, value)))
        log.info("RH          Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.RH, value)))
        log.info("WIND        Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.WIND,  value)))
        log.info("SOLARRAD    Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.SOLARRADIATION, value)))
        log.info("SKYCOVER    Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.SKYCOVER, value)))
        log.info("ET          Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.ET0, value)))
        log.info("QPF         Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.QPF, value)))
        log.info("RAIN        Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.RAIN, value)))
        log.info("PRESSURE    Sanitized %s to %s" % (value, l.sanitize(RMWeatherDataType.PRESSURE, value)))
        log.info("-" * 100)

