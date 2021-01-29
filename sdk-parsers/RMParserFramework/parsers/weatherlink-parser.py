# Copyright (c) 2018 George Bothwell
# All rights reserved.
# Author: George Bothwell <gcbothwell@gmail.com>
#
# This is a custom parser to read data from WiFiLogger attached to a Davis Vantage Vue
#

from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging
from RMUtilsFramework.rmTimeUtils import *
import json
import rfc822



class Weatherlink(RMParser):
    parserName = "Davis WeatherLink"
    parserDescription = "Davis Weatherlink.Com Weather Service"
    parserInterval = 6 * 3600  # delay between runs in seconds
    parserForecast = False
    parserHistorical = True
    parserEnabled = True
    parserDebug = False
    params = {
        "DeviceId": "",
        "Password": "",
        "APIToken": ""
    }

    def toCelsius(self, tempF):
        return (tempF - 32) * 5/9

    def perform(self):
        # https://www.weatherlink.com/static/docs/APIdocumentation.pdf
        # add URL with DID / PWD / Token
        # this can easily be put in the UI and passed to parser...

      #  https: // api.weatherlink.com / v1 / NoaaExt.json?user = DID & pass=ownerPW & apiToken = tokenID
        did = self.getParamAsString(self.params.get("DeviceId"))
        pwd = self.getParamAsString(self.params.get("Password"))
        token = self.getParamAsString(self.params.get("APIToken"))

        if did is None:
            self.lastKnownError = "Missing Device ID"
            log.error(self.lastKnownError)
            return False

        if pwd is None:
            self.lastKnownError = "Missing Device Password"
            log.error(self.lastKnownError)
            return False

        if token is None:
            self.lastKnownError = "Missing API Token"
            log.error(self.lastKnownError)
            return False

        url = "https://api.weatherlink.com/v1/NoaaExt.json?user=" + str(did) + "&pass=" + str(pwd) + "&apiToken=" + str(token)

        weatherlinkData = self.openURL(url)
        if weatherlinkData is None:
            self.lastKnownError = "No reponse from WeatherLink service"
            log.error(self.lastKnownError)
            return

        try:
            json_data = weatherlinkData.read()
            json_data = json_data.replace("'", "\"")
            current_weather_data = json.loads(json_data)
        except Exception:
            self.lastKnownError = "Invalid data received from WeatherLink service"
            log.error(self.lastKnownError)
            return False

        log.debug("Parsing Weatherlink Data...")

        # TIMESTAMP = "TIMESTAMP"  # [Unix timestamp]
        timestamp = float(rfc822.mktime_tz(rfc822.parsedate_tz(current_weather_data["observation_time_rfc822"])))
        #timestamp = current_weather_data["observation_time_rfc822"]
        log.debug("TIMESTAMP: %s" % (timestamp))

        # TEMPERATURE = "TEMPERATURE"  # [degC]
        TEMPERATURE = float(current_weather_data["temp_c"])
        log.debug("TEMPERATURE: %s" % (TEMPERATURE))
        self.addValue(RMParser.dataType.TEMPERATURE, timestamp, TEMPERATURE)

        current_observation = current_weather_data["davis_current_observation"]

        # MINTEMP = "MINTEMP"  # [degC]
        log.debug("minTempF: %s" % (current_observation["temp_day_low_f"]))
        MINTEMP = self.toCelsius(float(current_observation["temp_day_low_f"]))
        log.debug("MINTEMP: %s" % (MINTEMP))
        self.addValue(RMParser.dataType.MINTEMP, timestamp, MINTEMP)

        # MAXTEMP = "MAXTEMP"  # [degC]
        log.debug("maxTempF: %s" % (current_observation["temp_day_high_f"]))
        MAXTEMP = self.toCelsius(float(current_observation["temp_day_high_f"]))
        log.debug("MAXTEMP: %s" % (MAXTEMP))
        self.addValue(RMParser.dataType.MAXTEMP, timestamp, MAXTEMP)

        # RH = "RH"  # [percent]
        RH = current_weather_data["relative_humidity"]
        log.debug("RH: %s" % (RH))
        self.addValue(RMParser.dataType.RH, timestamp, RH)


        # MINRH = "MINRH"  # [percent]
        MINRH = current_observation["relative_humidity_day_low"]
        log.debug("MINRH: %s" % (MINRH))
        self.addValue(RMParser.dataType.MINRH, timestamp, MINRH)

        # MAXRH = "MAXRH"  # [percent]
        MAXRH = current_observation["relative_humidity_day_high"]
        log.debug("MAXRH: %s" % (MAXRH))
        self.addValue(RMParser.dataType.MAXRH, timestamp, MAXRH)

        # WIND = "WIND"  # [meter/sec]
        # here I will use the avg 10 minute speed, will convert from mph
        # 1 Mile per Hour =  0.44704 Meters per Second
        windMPH = float(current_observation["wind_ten_min_avg_mph"])
        log.debug("windMPH: %s" % (windMPH))

        WIND = windMPH * 0.44704
        log.debug("WIND: %s" % (WIND))
        self.addValue(RMParser.dataType.WIND, timestamp, WIND)

        # SOLARRADIATION = "SOLARRADIATION"  # [megaJoules / square meter per hour]
        # SKYCOVER = "SKYCOVER"  # [percent]

        # RAIN = "RAIN"  # [mm]
        # 1 inch = 25.4mm
        rainInch = float(current_observation["rain_day_in"])
        log.debug("rainInch: %s" % (rainInch))

        RAIN = rainInch * 25.4
        log.debug("RAIN: %s" % (RAIN))
        self.addValue(RMParser.dataType.RAIN, timestamp, RAIN)

        # ET0 = "ET0"  # [mm]
        # POP = "POP"  # [percent]
        # QPF = "QPF"  # [mm] -

        # PRESSURE = "PRESSURE"  # [kilo Pa atmospheric pressure]
        # 1 inch = 3.3864 kpa
        barInch = float(current_weather_data["pressure_in"])
        log.debug("barInch: %s" % (barInch))

        PRESSURE = barInch * 3.3864
        log.debug("PRESSURE: %s" % (PRESSURE))
        self.addValue(RMParser.dataType.PRESSURE, timestamp, PRESSURE)

        # DEWPOINT = "DEWPOINT"  # [degC]
        DEWPOINT = float(current_weather_data["dewpoint_c"])
        log.debug("DEWPOINT: %s" % (DEWPOINT))
        self.addValue(RMParser.dataType.DEWPOINT, timestamp, DEWPOINT)


        RAINRATE = float(current_observation["rain_rate_in_per_hr"])
        log.debug("RAINRATE: %s" % (RAINRATE))

        # here lets check rain rate
        if (0 < RAINRATE <= 0.098):
            self.addValue(RMParser.dataType.CONDITION, timestamp, RMParser.conditionType.LightRain)
            log.debug("Current Condition Light Rain")

        elif (0.098 < RAINRATE <= 0.39):
            self.addValue(RMParser.dataType.CONDITION, timestamp, RMParser.conditionType.RainShowers)
            log.debug("Current Condition Rain Showers")

        elif (RAINRATE > 0.39):
            self.addValue(RMParser.dataType.CONDITION, timestamp, RMParser.conditionType.HeavyRain)
            log.debug("Current Condition Heavy Rain")

    def getParamAsString(self, param):
        try:
            param = param.strip()
        except Exception:
            return None

        if not param:
            return None

        return param

if __name__ == "__main__":
    p = Weatherlink()
    p.perform()
