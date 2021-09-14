# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Gordon Larsen <gordon@the-larsens.ca>

import datetime
import json
import time

from RMDataFramework.rmUserSettings import globalSettings
from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmNowDateTime, rmGetStartOfDay
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm


class PWSWeather(RMParser):
    parserName = "Aeris Personal Weather Station"
    parserDescription = "Personal weather station contributor access from PWS Weather(Aeris)"
    parserForecast = True
    parserHistorical = True
    parserEnabled = True
    parserDebug = False
    parserInterval = 60 * 60 * 6

    params = {"clientID": ""
        , "Secret": ""
        , "useCustomStation": True
        , "customStationName": ""
        , "_nearbyStationsIDList": []
        , "_airportStationsIDList": []
        , "useSolarRadiation": True}

    apiURL = None
    jsonResponse = None
    lastKnownError = None

    def isEnabledForLocation(self, timezone, lat, long):
        return PWSWeather.parserEnabled

    def perform(self):
        timeNow = rmNowDateTime()
        timeYesterday = rmNowDateTime().fromordinal(timeNow.toordinal() - 1)
        yyyyy = timeYesterday.year
        mmy = timeYesterday.month
        ddy = timeYesterday.day
        yyyy = timeNow.year
        mm = timeNow.month
        dd = timeNow.day

        limit = 10

        self.params["_nearbyStationsIDList"] = []
        self.params["_airportStationsIDList"] = []
        clientID = self.params.get("clientID", None)
        if clientID is None or not clientID or not isinstance(clientID, str):
            log.error("No Client ID provided")
            self.lastKnownError = "Error: No Client ID provided"
            return

        secret = self.params.get("Secret", None)
        if secret is None or not secret or not isinstance(secret, str):
            log.error("No Secret provided")
            self.lastKnownError = "Error: No Secret provided"
            return

        if self.params.get("useCustomStation"):
            stationName = self.params.get("customStationName")
            if stationName is None or not stationName or not isinstance(stationName, str):
                stationName = ":auto"
                log.info("Station name not valid, using automatic location identifier")
            limit = 10
        else:
            stationName = ":auto"
            log.info("Station not set, using automatic location identifier")
            limit = 10

        stationName = stationName.replace(" ", "")

        apiURL = \
            "http://api.aerisapi.com/observations/summary/" + stationName + "?&format=json&radius=75mi&filter=allstations&limit=" + \
            str(limit) + "&client_id=" \
            + str(clientID) + "&client_secret=" + str(secret)

        self.jsonResponse = self.apiCall(apiURL)

        if self.jsonResponse['success']:
            # populate nearby stations

            if self.params.get("useCustomStation") and self.params.get("customStationName"):

                pass
            else:
                self.getNearbyStations(self.jsonResponse)
                return

            self.getStationData(self.jsonResponse)

        if self.params.get("useCustomStation") and self.params.get("useSolarRadiation"):
            pass
        elif self.params.get("useSolarRadiation"):
            log.warning("Unable to get solar radiation. You need to specify a pws.")

        if self.parserForecast:
            apiURL = \
                "http://api.aerisapi.com/forecasts/" + stationName + "?&format=json&filter=mdnt2mdnt&limit=7" + \
                "&client_id=" + str(clientID) + "&client_secret=" + str(secret)
            self.jsonResponse = self.apiCall(apiURL)

            self.__getSimpleForecast()

        return

    def getNearbyStations(self, jsonData):
        airportStations = {}
        pwsStations = {}
        llat = self.settings.location.latitude
        llon = self.settings.location.longitude

        try:
            for key in jsonData['response']:
                if len(key['id']) == 4:
                    airportStations.update({str(key['id']): key['loc']})
        except:
            log.warning("No airport stations found!")
            self.lastKnownError = "Warning: No airport stations found!"

        try:
            for key in jsonData['response']:
                if ("MID" in key['id']) or ("PWS" in key['id']):
                    pwsStations.update({str(key['id']): key['loc']})
        except:
            log.warning("No pws stations found!")
            self.lastKnownError = "Warning: No pws stations found!"

        if pwsStations:
            # arrStations = pwsStations["station"]
            for key in pwsStations:
                # print key
                # print pwsStations.get(key)['lat']
                distance = None
                lat = pwsStations.get(key)['lat']
                lon = pwsStations.get(key)['long']
                log.debug("lat: {}, lon: {}, llat: {}, llon: {}".format(lat, lon, llat, llon))

                if lat is not None and lon is not None:  # some airports don't report lat/lon
                    distance = distanceBetweenGeographicCoordinatesAsKm(lat, lon, llat, llon)
                    print (distance)

                if distance is not None:
                    distance = int(round(distance))
                    infoStr = "(" + str(distance) + "km" + "; lat=" + str(round(lat, 2)) + ", lon=" + str(
                        round(lon, 2)) + ")"
                else:
                    distance = -1
                    infoStr = "(unknown distance)"

                self.params["_nearbyStationsIDList"].append(key + infoStr)

        log.debug(self.params["_nearbyStationsIDList"])

        if airportStations:
            for key in airportStations:
                distance = None
                lat = airportStations.get(key)['lat']
                lon = airportStations.get(key)['long']
                log.debug("lat: {}, lon: {}, llat: {}, llon: {}".format(lat, lon, llat, llon))

                if lat is not None and lon is not None:  # some airports don't report lat/lon
                    distance = distanceBetweenGeographicCoordinatesAsKm(lat, lon, llat, llon)
                    print (distance)

                if distance is not None:
                    distance = int(round(distance))
                    infoStr = "(" + str(distance) + "km" + "; lat=" + str(round(lat, 2)) + ", lon=" + str(
                        round(lon, 2)) + ")"
                else:
                    distance = -1
                    infoStr = "(unknown distance)"

                self.params["_airportStationsIDList"].append(key + infoStr)

        log.debug(self.params["_airportStationsIDList"])

    def getStationData(self, jsonData):
        # daily summary for yesterday
        try:
            if self.params.get("useCustomStation"):
                dailysummary = jsonData["response"]["periods"][0]["summary"]
            else:
                dailysummary = jsonData["response"][0]["periods"][0]["summary"]

            log.debug("Daily Summary: {}".format(dailysummary))
            temperature = self.__toFloat(dailysummary["temp"]["avgC"])

            mintemp = self.__toFloat(dailysummary["temp"]["minC"])
            maxtemp = self.__toFloat(dailysummary["temp"]["maxC"])
            rh = self.__toFloat(dailysummary["rh"]["avg"])
            minrh = self.__toFloat(dailysummary["rh"]["min"])
            maxrh = self.__toFloat(dailysummary["rh"]["max"])
            dewpoint = self.__toFloat(dailysummary["dewpt"]["avgC"])
            wind = self.__toFloat(dailysummary["wind"]["avgKPH"])
            if wind is not None:
                wind = wind / 3.6  # convertred from kmetersph to mps

            maxpressure = self.__toFloat(dailysummary["pressure"]["maxMB"])
            minpressure = self.__toFloat(dailysummary["pressure"]["minMB"])
            pressure = None
            if maxpressure is not None and minpressure is not None:
                pressure = (maxpressure / 2 + minpressure / 2) / 10  # converted to from mb to kpa
            rain = self.__toFloat(dailysummary["precip"]["totalMM"])

            # time utc
            timestamp = dailysummary["range"]["maxTimestamp"]
            print(timestamp)
            timestampiso = dailysummary["range"]["maxDateTimeISO"]
            print("Observations for date: %s Temp: %s, Rain: %s" % (
                timestampiso[0:16].replace("T", " "), temperature, rain))

            timestamp = self.__parseDateTime(timestamp)

            self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temperature)
            self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp)
            self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp)
            self.addValue(RMParser.dataType.RH, timestamp, rh)
            self.addValue(RMParser.dataType.MINRH, timestamp, minrh)
            self.addValue(RMParser.dataType.MAXRH, timestamp, maxrh)
            self.addValue(RMParser.dataType.WIND, timestamp, wind)
            self.addValue(RMParser.dataType.RAIN, timestamp, rain)
            # self.addValue(RMParser.dataType.QPF, timestamp, rain) # uncomment to report measured rain as previous day QPF
            self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint)
            self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)

            if self.params.get("useSolarRadiation"):
                solarradiation = self.__toFloat(dailysummary["solrad"]["avgWM2"])
                # needs to be converted from watt/sqm*h to Joule/sqm
                if solarradiation is not None:
                    solarradiation *= 0.0864
                self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, solarradiation)

            log.debug(
                "temp {}, minT {}, maxT {}, rh {}, minrh {}, maxrh {}, dewpoint {}, wind (MPS) {}, maxpress {}, "
                "minpress {}, avgpress {}, rain {}, solrad {}".format(
                    temperature, mintemp, maxtemp, rh, minrh, maxrh, dewpoint, wind, maxpressure, minpressure, pressure,
                    rain, solarradiation))

        except:
            log.warning("Failed to get daily summary")
            self.lastKnownError = "Warning: Failed to get daily summary"

    def __getSimpleForecast(self):
        try:
            timetuple = datetime.datetime.fromtimestamp(int(time.time())).timetuple()
            timestamp = datetime.datetime(timetuple.tm_year, timetuple.tm_mon, timetuple.tm_mday)
            dayTimestamp = int(time.mktime(timestamp.timetuple()))
            maxDayTimestamp = dayTimestamp + globalSettings.parserDataSizeInDays * 86400
            simpleForecast = self.jsonResponse["response"][0]

            for key in simpleForecast["periods"]:
                log.debug(key)
                timestamp = self.__toInt(key["timestamp"])
                if timestamp is None:
                    continue

                timestamp = int(timestamp)

                if timestamp < maxDayTimestamp:
                    temperatureMax = self.__toFloat(key["maxTempC"])
                    temperatureMin = self.__toFloat(key["minTempC"])
                    wind = self.__toFloat(key["windSpeedKPH"])
                    if wind is not None:
                        wind = wind / 3.6  # convertred from kmetersph to meterps
                    humidity = self.__toFloat(key["humidity"])
                    qpf = self.__toFloat(key["precipMM"])
                    pop = self.convertToPercent(key["pop"])
                    dewpoint = self.__toFloat(key["avgDewpointC"])
                    condition = self.conditionConvert(key["weatherPrimaryCoded"], key["cloudsCoded"])

                    self.addValue(RMParser.dataType.QPF, timestamp, qpf)
                    self.addValue(RMParser.dataType.RH, timestamp, humidity)
                    self.addValue(RMParser.dataType.WIND, timestamp, wind)
                    self.addValue(RMParser.dataType.POP, timestamp, pop)
                    self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint)
                    self.addValue(RMParser.dataType.MINTEMP, timestamp, temperatureMin)
                    self.addValue(RMParser.dataType.MAXTEMP, timestamp, temperatureMax)
                    self.addValue(RMParser.dataType.CONDITION, timestamp, condition)

        except:
            log.error("Failed to get simple forecast")

    def __parseDateTime(self, timestamp, roundToHour=True):
        if timestamp is None:
            return None
        if roundToHour:
            return timestamp - (timestamp % 3600)
        else:
            return timestamp

    def conditionConvert(self, weathercodes, cloudcodes):
        temparr = str(weathercodes).split(":")

        log.debug("Weatherarray: {}, conditions: {}".format(temparr, cloudcodes))
        intensity = temparr[1]
        conditionStr = temparr[2]

        if (conditionStr == 'L') or (conditionStr == 'ZL'):
            return RMParser.conditionType.LightRain
        elif (conditionStr == 'R') or (conditionStr == 'RW') or (conditionStr == 'RS') or (conditionStr == 'ZR') or (
                conditionStr == 'WM'):
            if (intensity == 'H') or (intensity == 'VH'):
                return RMParser.conditionType.HeavyRain
            else:
                return RMParser.conditionType.LightRain
        elif 'M' in conditionStr:
            return RMParser.conditionType.LightRain
        elif 'BR' in conditionStr:
            return RMParser.conditionType.LightRain
        elif 'S' in conditionStr:
            return RMParser.conditionType.Snow
        elif 'IP' in conditionStr:
            return RMParser.conditionType.IcePellets
        elif 'A' in conditionStr:
            return RMParser.conditionType.IcePellets
        elif (conditionStr == 'F') or (conditionStr == 'ZF'):
            return RMParser.conditionType.Fog
        elif 'H' in conditionStr:
            return RMParser.conditionType.Haze
        elif 'T' in conditionStr:
            return RMParser.conditionType.Thunderstorm
        elif 'K' in conditionStr:
            return RMParser.conditionType.Smoke

        elif '' in conditionStr:
            if 'OV' in cloudcodes:
                return RMParser.conditionType.Overcast
            elif 'CL' in cloudcodes:
                return RMParser.conditionType.Fair
            elif 'SC' in cloudcodes:
                return RMParser.conditionType.Fair
            elif 'BK' in cloudcodes:
                return RMParser.conditionType.PartlyCloudy
            elif 'FW' in cloudcodes:
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

    def convertToPercent(self, f):
        try:
                return f * 100
        except:
                return None

    def apiCall(self, apiURL):

        try:
            d = self.openURL(apiURL)
            jsonContent = d.read()
            if jsonContent is None:
                log.debug("Failed to get Aeris JSON contents")
                self.lastKnownError = "Error: Bad response"
                return

            jsonResponse = (json.loads(jsonContent))
            if (jsonResponse['success']):
                return jsonResponse

        except OSError as err :
            log.error("Unable to open Aeris URL:{}".format(err))


if __name__ == "__main__":
    p = PWSWeather()
    p.perform()
