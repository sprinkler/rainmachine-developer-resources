# coding=utf-8
# Instituto Português do Mar e da Atmosfera parser for the RainMachine sprinkler controller.
#
# This parser was created to get local forecasts in Portugal from the Instituto Português do Mar e da Atmosfera (IPMA)
# available at https://api.ipma.pt/.
#
# Author: Pedro J. Pereira <pjpeartree@gmail.com>
#
# 20200209:
#   - Initial version
#
# LICENSE: GNU General Public License v3.0
# GitHub: https://github.com/pjpeartree/rainmachine-ipma


import json

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmTimeUtils import rmTimestampFromDateAsString
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm

IPMA_API_URL = "https://api.ipma.pt/"
IPMA_FORECAST_URL = "https://api.ipma.pt/json/alldata/{}.json"
IPMA_LOCATIONS_URL = "http://api.ipma.pt/json/locations.json"
MAX_STATION_DISTANCE = 10  # Max Distance in Km


class IPMA(RMParser):
    parserName = "Portuguese Weather Bureau"
    parserDescription = "Local forecasts in Portugal from the Instituto Português do Mar e da Atmosfera (IPMA)"
    parserForecast = True
    parserHistorical = False
    parserInterval = 3600 * 6
    parserEnabled = False
    parserDebug = False

    STATION = '_NearStation'
    STATION_ID = '_StationId'
    STATION_DISTANCE = '_StationDistance(Km)'
    params = {STATION: 'auto discover', STATION_ID: None, STATION_DISTANCE: MAX_STATION_DISTANCE}

    def isEnabledForLocation(self, timezone, lat, lon):
        return timezone == "Europe/Lisbon" or timezone == "Atlantic/Azores"

    def perform(self):
        station = self._get_station()
        if station is not None:
            forecast = self._get_forecast(station)
            if forecast is not None:
                self._add(forecast)

    def _get_station(self):
        if self.STATION_ID not in self.params.keys():
            self.params = IPMA.params
        station_id = self.params[self.STATION_ID]
        if station_id is not None:
            return station_id
        # Auto-discover the nearest station
        return self._discover_station()

    def _discover_station(self):
        lat = self.settings.location.latitude
        lon = self.settings.location.longitude
        stations = self.openURL(IPMA_LOCATIONS_URL)
        if stations is None:
            self._log_error("Error: Unable to fetch the station list from " + IPMA_LOCATIONS_URL)
            return None
        else:
            stations = json.loads(stations.read())
            for s in stations:
                s_lat = float(s['latitude'])
                s_lon = float(s['longitude'])
                d = distanceBetweenGeographicCoordinatesAsKm(s_lat, s_lon, lat, lon)
                if d < self.params[self.STATION_DISTANCE]:
                    self.params[self.STATION] = s['local']
                    self.params[self.STATION_ID] = s['globalIdLocal']
                    self.params[self.STATION_DISTANCE] = d
            if self.params[self.STATION_DISTANCE] == MAX_STATION_DISTANCE:
                self._log_error("Error: Unable to discover a nearby station")
                return None
            return self.params[self.STATION_ID]

    def _get_forecast(self, station):
        data = self.openURL(IPMA_FORECAST_URL.format(str(station)))
        if data is None:
            self._log_error("Error: No forecast data available at: " + IPMA_FORECAST_URL.format(str(station)))
            return data
        return json.loads(data.read())

    def _add(self, forecast):
        if len(forecast) == 0:
            self._log_error("Error: No forecast data found")
            return
        for entry in forecast:
            timestamp = rmTimestampFromDateAsString(entry["dataPrev"], "%Y-%m-%dT%H:%M:%S")
            maxtemp = self._read(entry["tMax"])
            mintemp = self._read(entry["tMin"])
            temp = self._read(entry["tMed"])
            humidity = self._read(entry["hR"])
            pop = self._read(entry["probabilidadePrecipita"])
            # IPMA gives wind in km/h but formula expects in m/s
            wind = self._read(entry["ffVento"])
            wind = wind / 3.6 if wind is not None else None  # [km/h] to [meter/sec]
            # Convert IPMA condition to RM condition
            condition = self._condition(entry["idTipoTempo"])

            self._store(RMParser.dataType.TEMPERATURE, timestamp, temp)  # TEMPERATURE # [degC]
            self._store(RMParser.dataType.MINTEMP, timestamp, mintemp)  # MINTEMP  # [degC]
            self._store(RMParser.dataType.MAXTEMP, timestamp, maxtemp)  # MAXTEMP # [degC]
            self._store(RMParser.dataType.RH, timestamp, humidity)  # RH # [percent]
            self._store(RMParser.dataType.WIND, timestamp, wind)  # WIND # [meter/sec]
            self._store(RMParser.dataType.POP, timestamp, pop)  # POP # [percent]
            self._store(RMParser.dataType.CONDITION, timestamp, condition)  # CONDITION # [string]

    def _store(self, key, timestamp, value):
        if value is not None:
            self.addValue(key, timestamp, value)

    @staticmethod
    def _read(value):
        if value == "-99.0" or value == -99.0:
            return None
        return float(value)

    # Weather Condition class available at http://api.ipma.pt/open-data/weather-type-classe.json
    @staticmethod
    def _condition(condition_id):
        if condition_id is None or condition_id == -99 or condition_id == 0:
            return RMParser.conditionType.Unknown
        if condition_id == 1:
            return RMParser.conditionType.Fair
        if condition_id == 2 or condition_id == 25:
            return RMParser.conditionType.PartlyCloudy
        if condition_id == 3:
            return RMParser.conditionType.FewClouds
        if condition_id == 4 or condition_id == 24 or condition_id == 27:
            return RMParser.conditionType.MostlyCloudy
        if condition_id == 5:
            return RMParser.conditionType.Overcast
        if condition_id == 6 or condition_id == 7 or condition_id == 8 or condition_id == 15:
            return RMParser.conditionType.RainShowers
        if condition_id == 10 or condition_id == 9 or condition_id == 13 or condition_id == 12:
            return RMParser.conditionType.LightRain
        if condition_id == 11 or condition_id == 14:
            return RMParser.conditionType.HeavyRain
        if condition_id == 16 or condition_id == 17 or condition_id == 26:
            return RMParser.conditionType.Fog
        if condition_id == 18:
            return RMParser.conditionType.Snow
        if condition_id == 19 or condition_id == 20 or condition_id == 23:
            return RMParser.conditionType.Thunderstorm
        if condition_id == 21:
            return RMParser.conditionType.RainIce
        if condition_id == 22:
            return RMParser.conditionType.FreezingRain
        return RMParser.conditionType.Unknown

    # Helper function to log errors
    def _log_error(self, message):
        self.lastKnownError = message
        log.error(self.lastKnownError)
