# coding: utf-8
# DWD parser for rainmachine
# Copyright (C) 2018  Sebastian Kuhn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging
from RMUtilsFramework.rmTimeUtils import rmNowDateTime, rmGetStartOfDay # helpers for date calculations
from RMUtilsFramework.rmTimeUtils import rmTimestampFromDateAsString # helper for timestamp creation
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
import csv  # needed for csv import
import urllib2

class DWDParser(RMParser):
    parserName = "DWD Parser"
    parserDescription = "Parser for the german \"Deutscher Wetterdienst\""
    parserForecast = True
    parserHistorical = True
    parserInterval = 6 * 3600
    parserDebug = False
    params = {"station": None}
    defaultParams = {"station": 10637}

    def perform(self):
        station = self.params.get("station", None)
        if station is None or station == "":
            url = "http://opendata.dwd.de/weather/local_forecasts/poi/10637-MOSMIX.csv"
            log.debug("No station set, using Frankfurt am Main (10637)")
        else:
            url = "http://opendata.dwd.de/weather/local_forecasts/poi/" + str(station) + "-MOSMIX.csv" 

        URLParams = [
            ("User-Agent", "RainMachine v2")
        ]

        # read weather data for the given station
        try:
            file = self.openURL(url, URLParams)
            if file is None:
                self.lastKnownError = "Cannot read data from DWD Service."
                return

            reader = csv.reader(file, delimiter=';')
            included_cols = [0, 1, 2, 3, 4, 5, 9, 14, 22, 31, 34]
            next(reader)
            next(reader)
            next(reader)
            for row in reader:
                content = list(row[i] for i in included_cols)
                #print(content)
                datestring = content[0]+':'+content[1]
                timestamp = rmTimestampFromDateAsString(datestring, '%d.%m.%y:%H:%M')
                yesterdayTimestamp = rmGetStartOfDay(timestamp - 12 * 60 * 60)
                if timestamp is None:
                    log.debug("Cannot convert timestamp: %s to unix timestamp" % datestring)
                    continue

                # Temperature
                self.addValue(RMParser.dataType.TEMPERATURE, timestamp, float(content[2].replace(",", ".")))

                # Dewpoint
                self.addValue(RMParser.dataType.DEWPOINT, timestamp, float(content[3].replace(",", ".")))

                # Max Temperature
                if content[4] != '---':
                    self.addValue(RMParser.dataType.MAXTEMP, yesterdayTimestamp, float(content[4].replace(",", ".")))

                # Min Temperature
                if content[5] != '---':
                    self.addValue(RMParser.dataType.MINTEMP, yesterdayTimestamp, float(content[5].replace(",", ".")))

                # Wind speed km/h -> m/s
                self.addValue(RMParser.dataType.WIND, timestamp, 0.27777777777778 * float(content[6].replace(",", ".")))

                # precipitation amount last hour in mm
                self.addValue(RMParser.dataType.QPF, timestamp, float(content[7].replace(",", ".")))

                # atmospheric pressure
                self.addValue(RMParser.dataType.PRESSURE, timestamp, float(content[9].replace(",", "."))/10)

        except Exception, e:
            log.error("*** Error running DWD parser")
            log.exception(e)

if __name__ == "__main__":
    p = DWDParser()
    p.perform()
