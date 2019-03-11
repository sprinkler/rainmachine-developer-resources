from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging

import json    # Your parser needed libraries

class ExampleParser(RMParser):
    parserName = "My Example Parser"  # Your parser name
    parserDescription = "Example parser for developers" # A short description of your parser
    parserForecast = False # True if parser provides future forecast data
    parserHistorical = True # True if parser also provides historical data (only actual observed data)
    parserInterval = 6 * 3600             # Your parser running interval in seconds, data will only be mixed in hourly intervals
    parserDebug = False
    params = {}

    def perform(self):                # The function that will be executed must have this name

        # Accessing system location settings
        lat = self.settings.location.latitude

        # Other location settings
        #self.zip
        #self.name
        #self.state
        #self.latitude
        #self.longitude
        #self.address
        #self.elevation
        #self.gmtOffset
        #self.dstOffset
        #self.stationID
        #self.stationName
        #self.et0Average

        # downloading data from a URL convenience function since other python libraries can be used
        # data = self.openURL(URL STRING, PARAMETER LIST)
        # URL = "https://example.com/
        # parameterList = [ ("parameter1", "value"),("parameter2", "value") ]

        # After parsing your data you can add it into a database automatically created for your parser with
        # self.addValue( VALUE TYPE, UNIX TIMESTAMP, VALUE)
        # Adding multiple values at once is possible with
        # self.addValues( VALUE TYPE, LIST OF TUPLES [ (TIMESTAMP, VALUE), (TIMESTAMP, VALUE) ... ]
        # Predefined VALUE TYPES
        # RMParser.dataType.TEMPERATURE
        # RMParser.dataType.MINTEMP
        # RMParser.dataType.MAXTEMP
        # RMParser.dataType.RH
        # RMParser.dataType.WIND
        # RMParser.dataType.SOLARRADIATION
        # RMParser.dataType.SKYCOVER
        # RMParser.dataType.RAIN
        # RMParser.dataType.ET0
        # RMParser.dataType.POP
        # RMParser.dataType.QPF
        # RMParser.dataType.CONDITION
        # RMParser.dataType.PRESSURE
        # RMParser.dataType.DEWPOINT


        # For your own custom values you can use
        # self.addUserValue( YOUR CUSTOM VALUE NAME, TIMESTAMP, VALUE)
