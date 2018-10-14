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


class WifiLogger(RMParser):
    parserName = "WifiLogger Parser"
    parserDescription = "WifiLogger Parser"
    parserInterval = 600  # delay between runs in seconds
    parserForecast = False
    parserHistorical = True
    parserEnabled = True
    parserDebug = False

    def toCelsius(self, tempF):
        return (tempF - 32) * 5/9

    def perform(self):

        # add URL FOR WiFiLogger connected to Davis Console...
        url = "http://10.123.1.120/wflexp.json"

        wifiLoggerData = self.openURL(url)
        if wifiLoggerData is None:
            return

        json_data = wifiLoggerData.read()

        json_data = json_data.replace("'", "\"")
        current_weather_data = json.loads(json_data)

        log.info("Parsing Wifi Logger Data...")

        # TIMESTAMP = "TIMESTAMP"  # [Unix timestamp]
        timestamp = current_weather_data["utctime"]
        log.debug("TIMESTAMP: %s" % (timestamp))

        # TEMPERATURE = "TEMPERATURE"  # [degC]
        temperatureF = float(current_weather_data["tempout"])
        log.debug("temperatureF: %s" % (temperatureF))

        TEMPERATURE = self.toCelsius(temperatureF)
        log.debug("TEMPERATURE: %s" % (TEMPERATURE))
        self.addValue(RMParser.dataType.TEMPERATURE, timestamp, TEMPERATURE)

        hltempout = current_weather_data["hltempout"]

        # MINTEMP = "MINTEMP"  # [degC]
        log.debug("minTempF: %s" % (hltempout[0]))

        MINTEMP = self.toCelsius(float(hltempout[0]))
        log.debug("MINTEMP: %s" % (MINTEMP))
        self.addValue(RMParser.dataType.MINTEMP, timestamp, MINTEMP)

        # MAXTEMP = "MAXTEMP"  # [degC]
        log.debug("maxTempF: %s" % (hltempout[1]))
        MAXTEMP = self.toCelsius(float(hltempout[1]))
        log.debug("MAXTEMP: %s" % (MAXTEMP))
        self.addValue(RMParser.dataType.MAXTEMP, timestamp, MAXTEMP)

        # RH = "RH"  # [percent]
        RH = current_weather_data["humout"]
        log.debug("RH: %s" % (RH))
        self.addValue(RMParser.dataType.RH, timestamp, RH)

        hltempout = current_weather_data["hlhumout"]
        # MINRH = "MINRH"  # [percent]
        MINRH = hltempout[0]
        log.debug("MINRH: %s" % (MINRH))
        self.addValue(RMParser.dataType.MINRH, timestamp, MINRH)

        # MAXRH = "MAXRH"  # [percent]
        MAXRH = hltempout[1]
        log.debug("MAXRH: %s" % (MAXRH))
        self.addValue(RMParser.dataType.MAXRH, timestamp, MAXRH)

        # WIND = "WIND"  # [meter/sec]
        # here I will use the avg 10 minute speed, will convert from mph
        # 1 Mile per Hour =  0.44704 Meters per Second
        windMPH = float(current_weather_data["windavg10"])
        log.debug("windMPH: %s" % (windMPH))

        WIND = windMPH * 0.44704
        log.debug("WIND: %s" % (WIND))
        self.addValue(RMParser.dataType.WIND, timestamp, WIND)

        # SOLARRADIATION = "SOLARRADIATION"  # [megaJoules / square meter per hour]
        # SKYCOVER = "SKYCOVER"  # [percent]

        # RAIN = "RAIN"  # [mm]
        # 1 inch = 25.4mm
        rainInch = float(current_weather_data["raind"])
        log.debug("rainInch: %s" % (rainInch))

        RAIN = rainInch * 25.4
        log.debug("RAIN: %s" % (RAIN))
        self.addValue(RMParser.dataType.RAIN, timestamp, RAIN)

        # ET0 = "ET0"  # [mm]
        # POP = "POP"  # [percent]
        # QPF = "QPF"  # [mm] -

        # PRESSURE = "PRESSURE"  # [kilo Pa atmospheric pressure]
        # 1 inch = 3.3864 kpa
        barInch = float(current_weather_data["bar"])
        log.debug("barInch: %s" % (barInch))

        PRESSURE = barInch * 3.3864
        log.debug("PRESSURE: %s" % (PRESSURE))
        self.addValue(RMParser.dataType.PRESSURE, timestamp, PRESSURE)

        # DEWPOINT = "DEWPOINT"  # [degC]
        dewF = float(current_weather_data["dew"])
        log.debug("dewF: %s" % (dewF))

        DEWPOINT = self.toCelsius(dewF)
        log.debug("DEWPOINT: %s" % (DEWPOINT))
        self.addValue(RMParser.dataType.DEWPOINT, timestamp, DEWPOINT)

        RAINRATE = float(current_weather_data["rainr"])
        log.debug("RAINRATE: %s" % (RAINRATE))

        # CONDITION = "CONDITION"  # [string]
        #
        # current conditions ... from Davis
        # Forecast Icon Values
        #
        # Value Decimal Value Hex Segments Shown Forecast
        currentConditionValue = int(current_weather_data["foreico"])

        # 8 0x08 Sun Mostly Clear
        # mapping to "Fair"
        if currentConditionValue == 8:
            self.addValue(RMParser.dataType.CONDITION, timestamp, RMParser.conditionType.Fair)
            log.debug("Current Condition Fair")

        # 6 0x06 Partial Sun + Cloud Partly Cloudy
        # 7 0x07 Partial Sun + Cloud + Rain Partly Cloudy, Rain within 12 hours
        # 22 0x16 Partial Sun + Cloud + Snow Partly Cloudy, Snow within 12 hours
        # 23 0x17 Partial Sun + Cloud + Rain + Snow Partly Cloudy, Rain or Snow within 12 hours
        # mapping to "PartlyCloudy"
        elif ((currentConditionValue == 6) or (currentConditionValue == 7) or (currentConditionValue == 22) or (currentConditionValue == 23)):
            self.addValue(RMParser.dataType.CONDITION, timestamp, RMParser.conditionType.PartlyCloudy)
            log.debug("Current Condition Partly Cloudy")

        # 2 0x02 Cloud Mostly Cloudy
        # 3 0x03 Cloud + Rain Mostly Cloudy, Rain within 12 hours
        # 18 0x12 Cloud + Snow Mostly Cloudy, Snow within 12 hours
        # 19 0x13 Cloud + Rain + Snow Mostly Cloudy, Rain or Snow within 12 hours
        # mapping to "MostlyCloudy"
        elif ((currentConditionValue == 2) or (currentConditionValue == 3) or (currentConditionValue == 18) or (currentConditionValue == 19)):
            self.addValue(RMParser.dataType.CONDITION, timestamp, RMParser.conditionType.MostlyCloudy)
            log.debug("Current Condition Mostly Cloudy")


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

# uncomment for testing
if __name__ == "__main__":
    p = WifiLogger()
    p.perform()
