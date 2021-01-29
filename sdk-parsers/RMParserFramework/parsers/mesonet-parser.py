from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp
import json    # Your parser needed libraries

class Mesonet(RMParser):
    parserName = "Mesonet"         # Your parser name
    parserDescription = "The Oklahoma Mesonet is a world-class network of environmental monitoring stations." # A description for this parser

    parserEnabled = True
    parserInterval = 3600                    # Your parser running interval in seconds
    parserDebug = True                      # Don't show extra debug messages
    params = {}                              # Internal params that can be changed with API call /parser/{id}/params

    def isEnabledForLocation(self, timezone, lat, long):
        return Mesonet.parserEnabled

    # The function that will be executed must have this name
    def perform(self):
        # downloading data from a URL convenience function since other python libraries can be used
        URL = "http://lab.zanek.net/mesonet/api/currentobservations"
        stationID = "ALTU"
        data = self.openURL(URL)


        if data is None:
            return

        stationsData = json.loads(data.read())

        if stationsData is None:
            self.lastKnownError = "Error: Invalid response from server"
            return

        timestamp = rmCurrentTimestamp()

        for station in stationsData:
            if station['STID'] == stationID:
                try:
                    rain = self.__toFloat(station.get("RAIN"))
                except:
                    rain = None

                try:
                    tmin = self.__toFloat(station.get("TMIN"))
                    tmax = self.__toFloat(station.get("TMAX"))
                except:
                    self.lastKnownError = "Error: No minimum or maximum temperature can be retrieved"
                    return

                try:
                    pressure = self.__toFloat(station.get("PRES"))
                except:
                    pressure = None

                try:
                    wind = self.__toFloat(station.get("WSPD"))
                except:
                    wind = None

                try:
                    dew = self.__toFloat(station.get("TDEW"))
                except:
                    dew = None

                self.addValue(RMParser.dataType.MINTEMP, timestamp, tmin)
                self.addValue(RMParser.dataType.MAXTEMP, timestamp, tmax)
                self.addValue(RMParser.dataType.RAIN, timestamp, rain)
                self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)
                self.addValue(RMParser.dataType.WIND, timestamp, wind)
                self.addValue(RMParser.dataType.DEWPOINT, timestamp, dew)

                if self.parserDebug:
                    log.debug(self.result)

    def __toFloat(self, value):
        if value is None:
            return value
        return float(value)