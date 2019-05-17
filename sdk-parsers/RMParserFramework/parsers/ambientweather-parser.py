# Ambient Weather Network parser for RainMachine smart sprinkler controller
#
# Feed your personal weather station data from ambientweather.net into your RainMachine
# Requires an API and application key, and the MAC address of your weather station.
#
# Author: Seth Mattinen <seth@mattinen.org>
#
# 20190324:
#   - first version using data from a WS-2000 with Osprey sensor array
#
# LICENSE: GNU General Public License v3.0
# GitHub: https://github.com/WillCodeForCats/rainmachine-amweather
#

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmUtils import convertFahrenheitToCelsius,convertInchesToMM,convertRadiationFromWattsToMegaJoules
import json


class AmbientWeatherParser(RMParser):
    parserName = "Ambient Weather Network Parser"
    parserDescription = "Live personal weather station data from www.ambientweather.net"
    parserForecast = False
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserInterval = 60 * 60  # hourly

    params = {"apiKey": None
        , "applicationKey": None
        , "macAddress": None}

    def perform(self):
        url = 'https://api.ambientweather.net/v1/devices/' + str(self.params["macAddress"])
        parameterList = [("apiKey", str(self.params["apiKey"]))
            , ("applicationKey", str(self.params["applicationKey"]))
            , ("limit", "1")]

        log.info('Getting data from {0}'.format(str(url)))
        data = self.openURL(url, parameterList)

        if data is None:
            self.lastKnownError = "Error: No data received from server"
            log.error(self.lastKnownError)
            return

        station = json.loads(data.read())
        for entry in station:
            dateutc = entry["dateutc"] / 1000  # from milliseconds

            if 'tempf' in entry:
                temp = convertFahrenheitToCelsius(entry["tempf"])
                self.addValue(RMParser.dataType.TEMPERATURE, dateutc, temp, False)
            
            if 'humidity' in entry:
                self.addValue(RMParser.dataType.RH, dateutc, entry["humidity"], False)
            
            if 'windspeedmph' in entry:
                windspeed = entry["windspeedmph"] * 0.44704  # to meters/sec
                self.addValue(RMParser.dataType.WIND, dateutc, windspeed, False)
            
            if 'solarradiation' in entry:
                solarrad = convertRadiationFromWattsToMegaJoules(entry["solarradiation"])
                self.addValue(RMParser.dataType.SOLARRADIATION, dateutc, solarrad, False)
            
            if 'dailyrainin' in entry:
                rain = convertInchesToMM(entry["dailyrainin"])
                self.addValue(RMParser.dataType.RAIN, dateutc, rain, False)

            if 'baromrelin' in entry:
                pressure = entry["baromrelin"] * 3.38639  # to kPa
                self.addValue(RMParser.dataType.PRESSURE, dateutc, pressure, False)
            
            if 'dewPoint' in entry:
                dewpoint = convertFahrenheitToCelsius(entry["dewPoint"])
                self.addValue(RMParser.dataType.DEWPOINT, dateutc, dewpoint, False)
        return True
