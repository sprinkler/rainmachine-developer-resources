# coding=utf-8
from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging

import csv

from RMUtilsFramework.rmTimeUtils import rmTimestampFromDateAsString


class ExampleParser(RMParser):
    parserName = "DWD Parser"  # Your parser name
    parserDescription = "Parser for the german \"Deutscher Wetterdienst\""  # A short description of your parser
    parserForecast = True # True if parser provides future forecast data
    parserHistorical = False # True if parser also provides historical data (only actual observed data)
    parserInterval = 6 * 3600             # Your parser running interval in seconds, data will only be mixed in hourly intervals
    parserDebug = False
    params = {"station": None}

    def perform(self):                # The function that will be executed must have this name

        station = self.params.get("station", None)
        if station is None:
            log.debug("No station set, using Frankfurt am Main" % datestring)
            station = 10637
        url = "http://opendata.dwd.de/weather/local_forecasts/poi/" + str(station) + "-MOSMIX.csv"

        URLParams = [
            ("User-Agent", "RainMachine v2")
        ]

        try:

            file = self.openURL(url, URLParams)
            if file is None:
                return

            reader = csv.reader(file, delimiter=';')
            included_cols = [0, 1, 2, 3, 4, 5, 9, 14, 22, 31, 34]
            next(reader)
            next(reader)
            next(reader)
            for row in reader:
                content = list(row[i] for i in included_cols)
                datestring = content[0]+':'+content[1]
                timestamp = rmTimestampFromDateAsString(datestring, '%d.%m.%y:%H:%M')
                if timestamp is None:
                    log.debug("Cannot convert timestamp: %s to unix timestamp" % datestring)
                    continue

                # Temperature
                self.addValue(RMParser.dataType.TEMPERATURE, timestamp, float(content[2].replace(",", ".")))

                # Dewpoint
                self.addValue(RMParser.dataType.DEWPOINT, timestamp, float(content[3].replace(",", ".")))

                # Max Temperature
                if content[4] != '---':
                    self.addValue(RMParser.dataType.MAXTEMP, timestamp, float(content[4].replace(",", ".")))

                # Min Temperature
                if content[5] != '---':
                    self.addValue(RMParser.dataType.MINTEMP, timestamp, float(content[5].replace(",", ".")))

                # Wind speed km/h -> m/s
                self.addValue(RMParser.dataType.WIND, timestamp, float(content[6].replace(",", "."))/3.6)

                # precipitation amount last hour in mm
                self.addValue(RMParser.dataType.QPF, timestamp, float(content[7].replace(",", ".")))

                # atmospheric pressure
                self.addValue(RMParser.dataType.PRESSURE, timestamp, float(content[9].replace(",", "."))/10)

                # Solar radiation kJ/m² => MJ/m²
                if content[10] != '---':
                    self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, float(content[10].replace(",", ".")))


        except Exception, e:
            log.error("*** Error running DWD parser")
            log.exception(e)


if __name__ == "__main__":
    p = ExampleParser()
    p.perform()
