# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmNowDateTime, rmGetStartOfDay, rmCurrentDayTimestamp, rmDeltaDayFromTimestamp
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType
import json


class WUnderground(RMParser):
    parserName = "WUnderground Parser"
    parserDescription = "Global weather service with personal weather station access from Weather Underground"
    parserForecast = True
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600

    # headers for retrival method of nearby stations and station data when we have no key
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'}

    params = {"apiKey" : None
              , "useCustomStation" : False
              , "customStationName": None
              , "_nearbyStationsIDList": []
              , "_airportStationsIDList": []
              , "_apiForecastDays" : 5}

    apiLocationURL = 'https://api.weather.com/v3/location/near?'
    apiStationSummaryURL = 'https://api.weather.com/v2/pws/dailysummary/7day?'
    apiStationCurrentURL = 'https://api.weather.com/v2/pws/observations/current?'
    apiForecastURL = 'https://api.weather.com/v3/wx/forecast/daily/' + str(params["_apiForecastDays"]) + 'day'

    apiURL = None
    jsonResponse = None

    def isEnabledForLocation(self, timezone, lat, long):
        return WUnderground.parserEnabled

    def perform(self):
        self.params["_nearbyStationsIDList"] = []
        self.params["_airportStationsIDList"] = []
        self.lastKnownError = ""
        apiKey = self.params.get("apiKey", None)
        useCustomStation = self.params.get("useCustomStation", False)
        stationName = self.params.get("customStationName")

        hasForecastData = False
        hasStationData = False
        noAPIKey = apiKey is None or not apiKey or not isinstance(apiKey, str)

        if noAPIKey:
            self.getNearbyStationsNoKey()
        else:
            self.getNearbyPWSStationsWithKey(apiKey)
            self.getNearbyAirportStationsWithKey(apiKey)
            hasForecastData = self.getForecastWithKey(apiKey)

        noStationName = stationName is None or not stationName or not isinstance(stationName, str)

        if useCustomStation:
            if stationName is None or not stationName or not isinstance(stationName, str):
                self.lastKnownError = "Warning: Use Nearby Stations is enabled but no station name specified."
                log.error(self.lastKnownError)
            else:
                self.arrStationNames = stationName.split(",")
                for stationName in self.arrStationNames:
                    if noAPIKey:
                        hasStationData = self.getStationDataNoKey(stationName)
                    else:
                        hasStationData = self.getStationDataWithKey(apiKey, stationName)

                    if hasStationData:  # we only get the first one that responds others are for fallback
                        break

                if not hasStationData:
                    self.lastKnownError = "Warning: No observed data received from stations."
                    if noAPIKey:
                        self.lastKnownError = "Error: No observed data received from stations."
                    log.error(self.lastKnownError)
                else:
                    log.info("WUnderground: station data retrieved for %s" % stationName)

        if not hasForecastData and not noAPIKey:
            self.lastKnownError = "Warning: No Forecast data received."
            if not hasStationData:
                self.lastKnownError = "Error: No forecast or station data received."
            log.error(self.lastKnownError)
        else:
            log.info("WUnderground: forecast data retrieved.")


    def getNearbyPWSStationsWithKey(self, apiKey):
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        stationsURL = self.apiLocationURL + 'geocode=' + str(llat) + ',' + str(llon) + '&product=pws&format=json&apiKey=' + str(apiKey)
        try:
            d = self.openURL(stationsURL)
            if d is None:
                self.lastKnownError = "Cannot download nearby pws stations"
                log.error(self.lastKnownError)
            stationsData = d.read()
            stations = json.loads(stationsData)
            self.parseNearbyStationsWithKey(stations)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get nearby pws stations"
            log.error(self.lastKnownError)
            return

    def getNearbyAirportStationsWithKey(self, apiKey):
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        stationsURL = self.apiLocationURL + 'geocode=' + str(llat) + ',' + str(llon) + '&product=airport&format=json&apiKey=' + str(apiKey)
        try:
            d = self.openURL(stationsURL)
            if d is None:
                self.lastKnownError = "Error: Cannot download nearby airport stations"
                log.error(self.lastKnownError)
            stationsData = d.read()
            stations = json.loads(stationsData)
            self.parseNearbyStationsWithKey(stations)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get airport stations"
            log.error(self.lastKnownError)
            return

    def parseNearbyStationsWithKey(self, stationsData):
        location = stationsData['location']
        arrStationId = location.get('stationId', None)
        pws = True
        if arrStationId is None:
            pws = False
            arrStationId = location.get('icaoCode', None)

        arrStationLat = location['latitude']
        arrStationLon = location['longitude']
        arrStationDistance = location['distanceKm']

        arrStations = []
        for index, stationId in enumerate(arrStationId):
            if stationId is None:
                continue
            arrStations.append({'id': stationId, 'lat': arrStationLat[index], 'lon': arrStationLon[index], 'distance': arrStationDistance[index]})
        arrStations = sorted(arrStations, key=lambda k: k['distance'])

        for stationDict in arrStations:
            if pws:
                self.params["_nearbyStationsIDList"].append(stationDict['id'] +  " (" + str(round(stationDict['distance'],1)) + "km" + "; lat=" +
                                                str(round(stationDict['lat'], 2)) + ", lon=" + str(round(stationDict['lon'], 2)) + ")")
            else:
                self.params["_airportStationsIDList"].append(
                    stationDict['id'] + " (" + str(round(stationDict['distance'], 1)) + "km" + "; lat=" +
                    str(round(stationDict['lat'], 2)) + ", lon=" + str(round(stationDict['lon'], 2)) + ")")

    def getStationDataWithKey(self, apiKey, stationName):
        observationURL = self.apiStationSummaryURL + 'stationId=' + str(stationName) + '&format=json&units=m&apiKey=' + str(apiKey)
        try:
            d = self.openURL(observationURL)
            if d is None:
                self.lastKnownError = "Cannot download station data"
                log.error(self.lastKnownError)
                return False
            stationData = d.read()
            observations = json.loads(stationData)
            return self.parseStationDataWithKey(observations)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get station data"
            log.error(self.lastKnownError)
            return False

    def parseStationDataWithKey(self, jsonData):
        # daily summary for yesterday
        tsToday = rmCurrentDayTimestamp()
        tsYesterDay = rmDeltaDayFromTimestamp(tsToday, -1)
        l = RMWeatherDataLimits()
        hasDataAdded = False
        try:
            dailysummary = jsonData['summaries']
            for observation in dailysummary:
                tsDay = observation.get('epoch', None)
                tsDay = rmGetStartOfDay(tsDay)

                temperature = self.__toFloat(observation['metric']['tempAvg'])
                mintemp = self.__toFloat(observation['metric']['tempLow'])
                maxtemp = self.__toFloat(observation['metric']['tempHigh'])
                rh = self.__toFloat(observation["humidityAvg"])
                minrh = self.__toFloat(observation["humidityLow"])
                maxrh = self.__toFloat(observation["humidityHigh"])
                dewpoint = self.__toFloat(observation['metric']["dewptAvg"])
                wind = self.__toFloat(observation['metric']["windspeedAvg"])
                if wind is not  None:
                     wind = wind / 3.6  # converted from kmetersph to mps

                maxpressure = self.__toFloat(observation['metric']["pressureMax"])
                minpressure = self.__toFloat(observation['metric']["pressureMin"])

                if maxpressure is not None:
                    maxpressure = l.sanitize(RMWeatherDataType.PRESSURE, maxpressure / 10.0)  # converted to from hpa to kpa

                if minpressure is not None:
                    minpressure = l.sanitize(RMWeatherDataType.PRESSURE, minpressure / 10.0)

                pressure = None
                if maxpressure is not None and minpressure is not None:
                    pressure = (maxpressure + minpressure) / 2.0

                rain = self.__toFloat(observation['metric']["precipTotal"])

                if tsDay == tsYesterDay:
                    self.addValue(RMParser.dataType.TEMPERATURE, tsDay, temperature, False)
                    self.addValue(RMParser.dataType.MINTEMP, tsDay, mintemp, False)
                    self.addValue(RMParser.dataType.MAXTEMP, tsDay, maxtemp, False)
                    self.addValue(RMParser.dataType.RH, tsDay, rh, False)
                    self.addValue(RMParser.dataType.MINRH, tsDay, minrh, False)
                    self.addValue(RMParser.dataType.MAXRH, tsDay, maxrh, False)
                    self.addValue(RMParser.dataType.WIND, tsDay, wind, False)
                    self.addValue(RMParser.dataType.RAIN, tsDay, rain, False)
                    self.addValue(RMParser.dataType.DEWPOINT, tsDay, dewpoint, False)
                    self.addValue(RMParser.dataType.PRESSURE, tsDay, pressure, False)
                    hasDataAdded = True
                elif tsDay == tsToday:
                    # For today data we only add RAIN which won't overwrite any forecast
                    # We add it at start of day since this entry should be updated at each parser run
                    # otherwise mixer will sum it up
                    self.addValue(RMParser.dataType.RAIN, tsDay, rain, False)
                    hasDataAdded = True
            return hasDataAdded
        except:
            self.lastKnownError = "Warning: Failed to get yesterday data summary"
            log.info(self.lastKnownError)
            return False

    def getStationDataCurrentWithKey(self, apiKey, stationName): # method for current observation
        observationURL = self.apiStationCurrentURL + 'stationId=' + str(stationName) + '&format=json&units=m&apiKey=' + str(apiKey)
        try:
            d = self.openURL(observationURL)
            if d is None:
                self.lastKnownError = "Cannot download station data"
                log.error(self.lastKnownError)
                return False
            stationData = d.read()
            observations = json.loads(stationData)
            # self.parseStationDataWithKey(observations)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get station data"
            log.error(self.lastKnownError)
            return

    def getForecastWithKey(self, apiKey):
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        forecastURL = self.apiForecastURL + '?geocode=' + str(llat) + ',' + str(llon) \
                      + '&language=en-US&units=m&format=json&apiKey=' + str(apiKey)
        try:
            d = self.openURL(forecastURL)
            if d is None:
                self.lastKnownError = "Cannot get forecast data"
                log.error(self.lastKnownError)
                return False
            forecastData = d.read()
            forecast = json.loads(forecastData)
            self.parseForecastWithKey(forecast)
            return True
        except Exception, e:
            self.lastKnownError = "Error: Cannot get forecast data"
            log.error(self.lastKnownError)
            return False

    def parseForecastWithKey(self, forecast):
        forecastDayPart = forecast.get('daypart', None)[0]
        arrIconCodeDP = forecastDayPart['iconCode'] # should get only odd icons/conditions for day part
        arrRelativeHumidityDP = forecastDayPart['relativeHumidity'] #interpolate max and min
        arrWindSpeddDP = forecastDayPart['windSpeed']

        arrTS = forecast['validTimeUtc']
        arrTemperatureMin = forecast['temperatureMin']
        arrTemperatureMax = forecast['temperatureMax']
        arrQPF = forecast['qpf']

        for index, timeStamp in enumerate(arrTS):
            mintemp = self.__toFloat(arrTemperatureMin[index])
            maxtemp = self.__toFloat(arrTemperatureMax[index])
            minrh = self.__toFloat(arrRelativeHumidityDP[2*index])
            maxrh = self.__toFloat(arrRelativeHumidityDP[2*index+1])
            windDay = arrWindSpeddDP[2*index]
            windNight = arrWindSpeddDP[2*index+1]
            wind = None
            if windDay is not None and windNight is not  None:
                wind = (self.__toFloat(windDay) + self.__toFloat(windNight)) / 2.
                wind = wind / 3.6  # converted from kmetersph to mps
            qpf = arrQPF[index]
            condition = self.conditionConvertWithKey(arrIconCodeDP[2 * index])

            if mintemp is not None:
                self.addValue(RMParser.dataType.MINTEMP, timeStamp, mintemp, False)
            if maxtemp is not None:
                self.addValue(RMParser.dataType.MAXTEMP, timeStamp, maxtemp, False)
            if minrh is not None:
                self.addValue(RMParser.dataType.MINRH, timeStamp, minrh, False)
            if maxrh is not None:
                self.addValue(RMParser.dataType.MAXRH, timeStamp, maxrh, False)
            if wind is not None:
                self.addValue(RMParser.dataType.WIND, timeStamp, wind, False)
            if qpf is not None:
                self.addValue(RMParser.dataType.QPF, timeStamp, qpf, False)
            if condition is not None:
                self.addValue(RMParser.dataType.CONDITION, timeStamp, condition, False)

    def conditionConvertWithKey(self, iconIndex):
        if iconIndex is None:
            return  None
        if iconIndex < 3:
            return RMParser.conditionType.FunnelCloud
        elif iconIndex < 5 or iconIndex == 38:
            return RMParser.conditionType.Thunderstorm
        elif iconIndex in (5, 7, 17, 18):
            return RMParser.conditionType.RainSnow
        elif iconIndex == 6:
            return RMParser.conditionType.RainIce
        elif iconIndex in (8, 10):
            return RMParser.conditionType.FreezingRain
        elif iconIndex in (9, 11, 35):
            return RMParser.conditionType.LightRain
        elif iconIndex in (12, 40):
            return RMParser.conditionType.HeavyRain
        elif iconIndex in (13, 14, 15, 16, 41, 42, 43, 46):
            return RMParser.conditionType.Snow
        elif iconIndex == 20:
            return RMParser.conditionType.Fog
        elif iconIndex == 21:
            return RMParser.conditionType.Haze
        elif iconIndex == 22:
            return RMParser.conditionType.Smoke
        elif iconIndex in (23, 24):
            return RMParser.conditionType.Windy
        elif iconIndex == 25:
            return RMParser.conditionType.IcePellets
        elif iconIndex == 26:
            return RMParser.conditionType.FewClouds
        elif iconIndex in (27, 28):
            return RMParser.conditionType.MostlyCloudy
        elif iconIndex in (29, 30):
            return RMParser.conditionType.PartlyCloudy
        elif iconIndex in (31, 32, 33, 34, 36):
            return RMParser.conditionType.Fair
        elif iconIndex in (37, 47):
            return RMParser.conditionType.ThunderstormInVicinity
        elif iconIndex in (39, 45):
            return RMParser.conditionType.RainShowers
        else:
            return RMParser.conditionType.Unknown

# NO API KEY
    def getStationDataNoKey(self, stationName):
        try:
            timeNow = rmNowDateTime()
            timeYesterday = rmNowDateTime().fromordinal(timeNow.toordinal() - 1)
            yyyyy = timeYesterday.year
            mmy = timeYesterday.month
            ddy = timeYesterday.day

            dataURL = "https://www.wunderground.com/weatherstation/WXDailyHistory.asp?ID=" + stationName + "&day=" + str(
                ddy) + "&month=" + str(mmy) + "&year=" + str(
                yyyyy) + "&graphspan=week&format=0&units=metric"

            d = self.openURL(dataURL, headers=self.headers)
            if d is None:
                log.error("Cannot download station %s data" % stationName)
                self.lastKnownError = "Error: Failed to get custom station"
                return False

            data = d.read()
            data = data.replace("\n<br>", "")
            data = data.replace("<br>", "")
            data = data[1:]
            arrLines = data.splitlines()

            valuesLine = None
            headerLine = arrLines[0]

            # first line is the header
            dateString = str(yyyyy) + '-' + str(mmy) + '-' + str(ddy)

            for line in arrLines:
                if line.startswith(dateString):
                    valuesLine = line
                    break
            headers = headerLine.split(',')
            values = valuesLine.split(',')
            dictValues = dict(zip(headers, values))

            self.parseStationYesterdayDataNoKey(dictValues)
            return True
        except:
            return False

    def getNearbyStationsNoKey(self):
        MIN_STATIONS = 1
        MAX_STATIONS = 20
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        stationsURL = "https://stationdata.wunderground.com/cgi-bin/stationdata?v=2.0&type=ICAO%2CPWS&units=metric&format=json&maxage=1800&maxstations=" \
                      + str(MAX_STATIONS) + "&minstations=" + str(MIN_STATIONS) + "&centerLat=" + str(llat) + "&centerLon=" \
                      + str(llon) + "&height=400&width=400&iconsize=2&callback=__ng_jsonp__.__req1.finished"
        try:
            # WARNING: WE PROBABLY SHOULD FAIL IF WE CAN'T GET STATIONS IF USER KNOWS STATION_ID
            log.debug("Downloading station data from: %s" % stationsURL)
            d = self.openURL(stationsURL, headers=self.headers)
            if d is None:
                self.lastKnownError = "Cannot download nearby stations"
                log.error(self.lastKnownError)
            # extract object from callback parameter
            stationsData = d.read()
            stationsObj = stationsData[stationsData.find("{"):stationsData.rfind("}") + 1]
            # log.info(stationsObj)
            stations = json.loads(stationsObj)
            self.parseNearbyStationsNoKey(stations)
        except Exception, e:
            self.lastKnownError = "ERROR: Cannot get nearby stations"
            log.error(self.lastKnownError)
            return

    def parseNearbyStationsNoKey(self, jsonData):
        stations = jsonData["stations"]
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        arrStations = []
        for stationDict in stations:
            stationId = stationDict["id"]
            stationType = stationDict["type"]
            if stationType == "PWS":
                lat1 = stationDict["latitude"]
                lon1 = stationDict["longitude"]
                distance = distanceBetweenGeographicCoordinatesAsKm(lat1, lon1, llat, llon)
                arrStations.append({'id':stationId, 'lat':lat1, 'lon':lon1, 'distance':distance})

        arrStations = sorted(arrStations, key=lambda k: k['distance'])
        for stationDict in arrStations:
            self.params["_nearbyStationsIDList"].append(stationDict['id'] +  " (" + str(round(stationDict['distance'],1)) + "km" + "; lat=" +
                                                str(round(stationDict['lat'], 2)) + ", lon=" + str(round(stationDict['lon'], 2)) + ")")

    def parseStationYesterdayDataNoKey(self, data):
        #daily summary for yesterday
        try:
            l = RMWeatherDataLimits()

            temperature = self.__toFloat(data["TemperatureAvgC"])
            mintemp = self.__toFloat(data["TemperatureLowC"])
            maxtemp = self.__toFloat(data["TemperatureHighC"])
            rh = self.__toFloat(data["HumidityAvg"])
            minrh = self.__toFloat(data["HumidityLow"])
            maxrh = self.__toFloat(data["HumidityHigh"])
            dewpoint = self.__toFloat(data["DewpointAvgC"])
            wind = self.__toFloat(data["WindSpeedAvgKMH"])
            maxpressure = self.__toFloat(data["PressureMaxhPa"])
            minpressure = self.__toFloat(data["PressureMinhPa"])
            rain = self.__toFloat(data["PrecipitationSumCM"]) * 10.0  # from cm to mm

            if wind is not None:
                wind = wind / 3.6  # converted from kmetersph to mps

            if maxpressure is not None:
                maxpressure = l.sanitize(RMWeatherDataType.PRESSURE, maxpressure / 10.0) # converted to from hpa to kpa

            if minpressure is not None:
                minpressure = l.sanitize(RMWeatherDataType.PRESSURE, minpressure / 10.0)

            pressure = None
            if maxpressure is not None and minpressure is not None:
                pressure = (maxpressure + minpressure) / 2.0

            #log.info("rh:%s minrh: %s maxrh: %s pressure: %s temp: %s mintemp: %s maxtemp: %s" % (rh, minrh, maxrh, pressure, temperature, mintemp, maxtemp))

            timestamp = rmCurrentDayTimestamp()
            timestamp = rmGetStartOfDay(timestamp - 12*3600)

            self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temperature, False)
            self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp, False)
            self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp, False)
            self.addValue(RMParser.dataType.RH, timestamp, rh, False)
            self.addValue(RMParser.dataType.MINRH, timestamp, minrh, False)
            self.addValue(RMParser.dataType.MAXRH, timestamp, maxrh, False)
            self.addValue(RMParser.dataType.WIND, timestamp, wind, False)
            self.addValue(RMParser.dataType.RAIN, timestamp, rain, False)
            self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint, False)
            self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure, False)

        except Exception, e:
            self.lastKnownError = "ERROR: Failed to get historical data"
            log.error("%s: %s" % (self.lastKnownError, e))

    def __parseDateTime(self, timestamp, roundToHour = True):
        if timestamp is None:
            return None
        if roundToHour:
            return timestamp - (timestamp % 3600)
        else:
            return timestamp

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

