# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmNowDateTime
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
from RMDataFramework.rmUserSettings import globalSettings
import json,time
import datetime, calendar


class WUnderground(RMParser):
    parserName = "WUnderground Parser"
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600

    params = {"apiKey" : None
              , "useCustomStation" : False
              , "customStationName": None
              , "_nearbyStationsIDList": []
              , "_airportStationsIDList": []}
    apiURL = None
    jsonResponse = None

    def isEnabledForLocation(self, timezone, lat, long):
        return WUnderground.parserEnabled

    def perform(self):

        timeNow = rmNowDateTime()
        timeNow = rmNowDateTime().fromordinal(timeNow.toordinal()-1)
        yyyy = timeNow.year
        mm = timeNow.month
        dd = timeNow.day

        log.debug("Wunderground parser - perform")

        self.params["_nearbyStationsIDList"] = []
        self.params["_airportStationsIDList"] = []

        apiKey =  self.params.get("apiKey", None)
        if(apiKey is None or not apiKey or not isinstance(apiKey, str)):
            #TODO: implement xml WUnderground parser
            log.error("No API Key provided")
            self.lastKnownError = "Error: No API Key provided"
            return

        self.apiURL = "http://api.wunderground.com/api/" + str(apiKey) + "/geolookup/conditions/hourly10day/history_" + str(yyyy) + str(mm).zfill(2) + str(dd).zfill(2) +"/q/"

        if (self.params.get("useCustomStation")):
            stationName = self.params.get("customStationName")
            if(stationName is None or not stationName or not isinstance(stationName, str)):
                log.error("Station ID cannot be empty")
                self.lastKnownError = "Error: Station ID cannot be empty"
                return
            log.debug("getting data from specified station")
            if len(stationName) > 4:
                self.apiURL += "pws:" + stationName + ".json" #url for pws
            else:
                self.apiURL += stationName + ".json" #url for pws
        else:
            s = self.settings
            llat = s.location.latitude
            llon = s.location.longitude
            self.apiURL +=  str(llat) + "," + str(llon) + ".json"

        # self.params["useCustomStation"] = False

        log.debug(self.apiURL)
        d = self.openURL(self.apiURL)
        jsonContent = d.read()
        if jsonContent is None:
            log.error("Failed to get WUnderground JSON contents")
            self.lastKnownError = "Error: Bad response"
            return

        self.jsonResponse = json.loads(jsonContent)

        #populate nearby stations
        log.debug("Wunderground parser - get nearby stations")
        self.getNearbyStations(self.jsonResponse)

        log.debug("Wunderground parser - get data")
        self.getStationData(self.jsonResponse)

        return

    def getNearbyStations(self, jsonData):

        nearbyStations = jsonData["location"][ "nearby_weather_stations"]
        airportStations = None
        pwsStations = None
        try:
            airportStations = nearbyStations["airport"]
        except:
            log.warning("No airport stations found!")
            self.lastKnownError = "Warning: No airport stations found!"
        try:
            pwsStations = nearbyStations["pws"]
        except:
            log.warning("No pws stations found!")
            self.lastKnownError = "Warning: No pws stations found!"

        if(pwsStations is not None):
            arrStations = pwsStations["station"]
            for st in arrStations:
                self.params["_nearbyStationsIDList"].append(str(st["id"]) + "(" + str(st["distance_km"]) + "km" + "; lat=" + str(round(st["lat"],2)) + ", lon=" + str(round(st["lon"],2)) + ")")

        if(airportStations is not None):
            arrStations = airportStations["station"]
            for st in arrStations:
                distance = None

                if not st["icao"]:
                    continue

                lat = self.__toFloat(st["lat"])
                lon = self.__toFloat(st["lon"])
                llat = self.settings.location.latitude
                llon = self.settings.location.longitude

                if lat is not None and lon is not None:  # some airports don't report lat/lon
                    distance = distanceBetweenGeographicCoordinatesAsKm(lat, lon, llat, llon)

                if distance is not None:
                    distance = self.__toInt(round(distance))
                else:
                    distance = -1

                self.params["_airportStationsIDList"].append(str(st["icao"]) + "(" + str(distance) + "km" + "; lat=" + str(round(lat,2)) + ", lon=" + str(round(lon,2)) + ")" )

        return self.params["_nearbyStationsIDList"]

    def getStationData(self, jsonData):

        #daily summary
        try:
            dailysummary = jsonData["history"]["dailysummary"][0]
            temperature = self.__toFloat(dailysummary["meantempm"])
            mintemp = self.__toFloat(dailysummary["mintempm"])
            maxtemp = self.__toFloat(dailysummary["maxtempm"])
            rh = self.__toFloat(dailysummary["humidity"])
            minrh = self.__toFloat(dailysummary["minhumidity"])
            maxrh = self.__toFloat(dailysummary["maxhumidity"])
            dewpoint = self.__toFloat(dailysummary["meandewptm"])
            wind = self.__toFloat(dailysummary["meanwindspdm"]) / 3.6 # convertred from kmetersph to meterps
            pressure = self.__toFloat(dailysummary["maxpressurem"])/2 + self.__toFloat(dailysummary["minpressurem"])/2 # to be compared
            rain = self.__toFloat(dailysummary["precipm"])
            solarradiation = self.__toFloat(jsonData["current_observation"]["solarradiation"])  #to be compared

            condition = self.conditionConvert(jsonData["current_observation"]["weather"])
            log.debug("Wunderground parser - got daily data")

            #time utc
            jutc = jsonData["history"]["utcdate"]
            yyyy = self.__toInt(jutc["year"])
            mm = self.__toInt(jutc["mon"])
            dd = self.__toInt(jutc["mday"])
            hour = self.__toInt(jutc["hour"])
            mins = self.__toInt(jutc["min"])
            log.debug("Wunderground parser - got time")

            dd = datetime.datetime(yyyy, mm, dd, hour, mins)
            timestamp = calendar.timegm( dd.timetuple())

            timestamp = self.__parseDateTime(timestamp)

            self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temperature)
            self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp)
            self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp)
            self.addValue(RMParser.dataType.RH, timestamp, rh)
            self.addValue(RMParser.dataType.MINRH, timestamp, minrh)
            self.addValue(RMParser.dataType.MAXRH, timestamp, maxrh)
            self.addValue(RMParser.dataType.WIND, timestamp, wind)
            self.addValue(RMParser.dataType.RAIN, timestamp, rain)
            self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint)
            self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)
            self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, solarradiation)
            self.addValue(RMParser.dataType.CONDITION, timestamp, condition)

        except:
            log.warning("Failed to get daily summary")
            self.lastKnownError = "Warning: Failed to get daily summary"

        try:
            #forecast hourly
            tuple = datetime.datetime.fromtimestamp(int(time.time())).timetuple()
            dayTimestamp = int(datetime.datetime(tuple.tm_year, tuple.tm_mon, tuple.tm_mday).strftime("%s"))
            maxDayTimestamp = dayTimestamp + globalSettings.parserDataSizeInDays * 86400
            forecastArrray = jsonData["hourly_forecast"]

            timestampF = []
            temperatureF = []
            depointF = []
            windF = []
            humidityF = []
            qpf = []
            conditionF = []
            log.debug("Wunderground parser - getting forecast")
            for hourF in forecastArrray:
                tt = self.__toInt(hourF["FCTTIME"]["epoch"])
                if(tt > maxDayTimestamp):
                    break
                timestampF.append(self.__toInt(tt))
                temperatureF.append(self.__toFloat(hourF["temp"]["metric"]))
                depointF.append(self.__toFloat(hourF["dewpoint"]["metric"]))
                windF.append(self.__toFloat(hourF["wspd"]["metric"])/ 3.6)   # convertred from kmetersph to meterps
                humidityF.append(self.__toFloat(hourF["humidity"]))
                qpf.append(self.__toFloat(hourF["qpf"]["metric"]))
                conditionF.append(self.conditionConvert(hourF["condition"]))

            temperatureF = zip(timestampF, temperatureF)
            depointF = zip(timestampF, depointF)
            windF = zip(timestampF, windF)
            humidityF = zip(timestampF, humidityF)
            qpf = zip(timestampF, qpf)
            conditionF = zip(timestampF, conditionF)

            self.addValues(RMParser.dataType.RH, humidityF)
            self.addValues(RMParser.dataType.TEMPERATURE, temperatureF)
            self.addValues(RMParser.dataType.QPF, qpf)
            self.addValues(RMParser.dataType.DEWPOINT, depointF)
            self.addValues(RMParser.dataType.WIND, windF)
            self.addValues(RMParser.dataType.CONDITION, conditionF)

            log.debug("Wunderground parser - got forecast")
        except:
            log.error("Failed to get forecast!")
            self.lastKnownError = "Error: Failed to get forecast"

        return

    def __parseDateTime(self, timestamp, roundToHour = True):
        if timestamp is None:
            return None
        if roundToHour:
            return timestamp - (timestamp % 3600)
        else:
            return timestamp

    def conditionConvert(self, conditionStr):
        if 'Drizzle' in conditionStr:
            return RMParser.conditionType.LightRain
        elif 'Chance of Rain' in conditionStr:
            return RMParser.conditionType.LightRain
        elif 'Light Rain' in conditionStr:
            return RMParser.conditionType.LightRain
        elif 'Heavy Rain' in conditionStr:
            return RMParser.conditionType.HeavyRain
        elif 'Rain' in conditionStr:
            return RMParser.conditionType.LightRain
        elif 'Snow' in conditionStr:
            return RMParser.conditionType.Snow
        elif 'Ice Pellets' in conditionStr:
            return RMParser.conditionType.IcePellets
        elif 'Hail' in conditionStr:
            return RMParser.conditionType.IcePellets
        elif 'Mist' in conditionStr:
            return RMParser.conditionType.Haze
        elif 'Fog' in conditionStr:
            return RMParser.conditionType.Fog
        elif 'Haze' in conditionStr:
            return RMParser.conditionType.Haze
        elif 'Thunderstorm' in conditionStr:
            return RMParser.conditionType.Thunderstorm
        elif 'Funel Cloud' in conditionStr:
            return RMParser.conditionType.FunnelCloud
        elif 'Overcast' in conditionStr:
            return RMParser.conditionType.Overcast
        elif 'Clear' in conditionStr:
            return RMParser.conditionType.Fair
        elif 'Partly Cloudy' in conditionStr:
            return RMParser.conditionType.PartlyCloudy
        elif 'Mostly Cloudy' in conditionStr:
            return RMParser.conditionType.MostlyCloudy
        elif 'Scattered Cloudy' in conditionStr:
            return RMParser.conditionType.PartlyCloudy
        elif 'Smoke' in conditionStr:
            return RMParser.conditionType.Smoke
        elif 'Clear' in conditionStr:
            return RMParser.conditionType.Fair
        else:
            return RMParser.conditionType.Unknown


    def __toFloat(self, value):
        try:
            if value is None:
                return value
            return float(value)
        except:
            return None

    def __toInt(self, value):
        try:
            if value is None:
                return value
            return int(value)
        except:
            return None

