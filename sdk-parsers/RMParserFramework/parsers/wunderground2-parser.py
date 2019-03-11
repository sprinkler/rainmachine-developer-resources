# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmNowDateTime, rmGetStartOfDay
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
from RMDataFramework.rmUserSettings import globalSettings
import json,time
import datetime, calendar


class WUnderground2(RMParser):
    parserName = "WUnderground Secondary Parser"
    parserDescription = "Global weather service with personal weather station access from Weather Underground"
    parserForecast = True
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600

    params = {"apiKey" : None
              , "useCustomStation" : False
              , "customStationName": None
              , "_nearbyStationsIDList": []
              , "_airportStationsIDList": []
              , "useSolarRadiation" :False}
    apiURL = None
    jsonResponse = None

    def isEnabledForLocation(self, timezone, lat, long):
        return WUnderground2.parserEnabled

    def perform(self):
        timeNow = rmNowDateTime()
        timeYesterday = rmNowDateTime().fromordinal(timeNow.toordinal()-1)
        yyyyy = timeYesterday.year
        mmy = timeYesterday.month
        ddy = timeYesterday.day
        yyyy = timeNow.year
        mm = timeNow.month
        dd = timeNow.day


        self.params["_nearbyStationsIDList"] = []
        self.params["_airportStationsIDList"] = []

        apiKey =  self.params.get("apiKey", None)
        if apiKey is None or not apiKey or not isinstance(apiKey, str):
            log.error("No API Key provided")
            self.lastKnownError = "Error: No API Key provided"
            return

        self.apiURL = "http://api.wunderground.com/api/" + str(apiKey) + "/geolookup/conditions/forecast10day/yesterday/q/"

        # / history_
        # " \
        #     + str(yyyyy) + str(mmy).zfill(2) + str(ddy).zfill(2)\
        #     + str(yyyy) + str(mm).zfill(2) + str(dd).zfill(2)+" / q / "

        if self.params.get("useCustomStation"):
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

        log.debug(self.apiURL)
        d = self.openURL(self.apiURL)
        jsonContent = d.read()
        if jsonContent is None:
            log.error("Failed to get WUnderground JSON contents")
            self.lastKnownError = "Error: Bad response"
            return

        self.jsonResponse = json.loads(jsonContent)

        #populate nearby stations
        self.getNearbyStations(self.jsonResponse)

        self.getStationData(self.jsonResponse)

        if self.params.get("useCustomStation") and self.params.get("useSolarRadiation"):
            self.__getSolarRadiation()
        elif self.params.get("useSolarRadiation"):
            log.warning("Unable to get solar radiation. You need to specify a pws.")

        return

    def getNearbyStations(self, jsonData):
        try:
            nearbyStations = jsonData["location"][ "nearby_weather_stations"]
        except:
            log.warning("No nearby stations found!")
            self.lastKnownError = "Warning: No nearby stations found!"
            return

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

        if pwsStations is not None:
            arrStations = pwsStations["station"]
            for st in arrStations:
                self.params["_nearbyStationsIDList"].append(str(st["id"]) + "(" + str(st["distance_km"]) + "km" + "; lat=" + str(round(st["lat"],2)) + ", lon=" + str(round(st["lon"],2)) + ")")

        if airportStations is not None:
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
                    infoStr = "(" + str(distance) + "km" + "; lat=" + str(round(lat, 2)) + ", lon=" + str(round(lon, 2)) + ")"
                else:
                    distance = -1
                    infoStr = "(unknown distance)"

                self.params["_airportStationsIDList"].append(str(st["icao"]) + infoStr)

    def getStationData(self, jsonData):
        #daily summary for yesterday
        try:
            dailysummary = jsonData["history"]["dailysummary"][0]
            temperature = self.__toFloat(dailysummary["meantempm"])
            mintemp = self.__toFloat(dailysummary["mintempm"])
            maxtemp = self.__toFloat(dailysummary["maxtempm"])
            rh = self.__toFloat(dailysummary["humidity"])
            minrh = self.__toFloat(dailysummary["minhumidity"])
            maxrh = self.__toFloat(dailysummary["maxhumidity"])
            dewpoint = self.__toFloat(dailysummary["meandewptm"])
            wind = self.__toFloat(dailysummary["meanwindspdm"])
            if wind is not  None:
                wind = wind / 3.6 # convertred from kmetersph to mps

            maxpressure = self.__toFloat(dailysummary["maxpressurem"])
            minpressure = self.__toFloat(dailysummary["minpressurem"])
            pressure = None
            if maxpressure is not None and minpressure is not None:
                pressure = (maxpressure/2 + minpressure/2) / 10 #converted to from mb to kpa

            rain = self.__toFloat(dailysummary["precipm"])

            #time utc
            jutc = jsonData["history"]["utcdate"]
            yyyy = self.__toInt(jutc["year"])
            mm = self.__toInt(jutc["mon"])
            dd = self.__toInt(jutc["mday"])
            hour = self.__toInt(jutc["hour"])
            mins = self.__toInt(jutc["min"])
            log.debug("Observations for date: %d/%d/%d Temp: %s, Rain: %s" % (yyyy, mm, dd, temperature, rain))

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
            # self.addValue(RMParser.dataType.QPF, timestamp, rain) # uncomment to report measured rain as previous day QPF
            self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint)
            self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)

        except:
            log.warning("Failed to get daily summary")
            self.lastKnownError = "Warning: Failed to get daily summary"

        self.__getSimpleForecast()

    def __getForecastHourly(self, jsonData):
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

            for hourF in forecastArrray:
                tt = self.__toInt(hourF["FCTTIME"]["epoch"])
                if tt > maxDayTimestamp:
                    break
                timestampF.append(self.__toInt(tt))
                temperatureF.append(self.__toFloat(hourF["temp"]["metric"]))
                depointF.append(self.__toFloat(hourF["dewpoint"]["metric"]))
                wind = self.__toFloat(hourF["wspd"]["metric"])
                if wind is not None:
                    windF.append(wind/ 3.6)   # convertred from kmetersph to meterps
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

        except:
            log.error("Failed to get hourly forecast!")
            self.lastKnownError = "Error: Failed to get forecast"

    def __getSimpleForecast(self):
        try:
            tuple = datetime.datetime.fromtimestamp(int(time.time())).timetuple()
            dayTimestamp = int(datetime.datetime(tuple.tm_year, tuple.tm_mon, tuple.tm_mday).strftime("%s"))
            maxDayTimestamp = dayTimestamp + globalSettings.parserDataSizeInDays * 86400
            simpleForecast = self.jsonResponse["forecast"]["simpleforecast"]["forecastday"]

            timestamp = []
            temperatureMax = []
            temperatureMin = []
            wind = []
            humidity = []
            qpf = []
            condition = []

            for dayF in simpleForecast:
                tt = self.__toInt(dayF["date"]["epoch"])
                tt = rmGetStartOfDay(tt)
                if tt > maxDayTimestamp:
                    break
                timestamp.append(self.__toInt(tt))
                temperatureMax.append(self.__toFloat(dayF["high"]["celsius"]))
                temperatureMin.append(self.__toFloat(dayF["low"]["celsius"]))
                windValue = self.__toFloat(dayF["avewind"]["kph"])
                if windValue is not None:
                    wind.append(windValue / 3.6)  # convertred from kmetersph to meterps
                humidity.append(self.__toFloat(dayF["avehumidity"]))
                qpf.append(self.__toFloat(dayF["qpf_allday"]["mm"]))
                condition.append(self.conditionConvert(dayF["conditions"]))

            temperatureMax = zip(timestamp, temperatureMax)
            temperatureMin = zip(timestamp, temperatureMin)
            wind = zip(timestamp, wind)
            humidity = zip(timestamp, humidity)
            qpf = zip(timestamp, qpf)
            condition = zip(timestamp, condition)

            self.addValues(RMParser.dataType.RH, humidity)
            self.addValues(RMParser.dataType.MAXTEMP, temperatureMax)
            self.addValues(RMParser.dataType.MINTEMP, temperatureMin)
            self.addValues(RMParser.dataType.QPF, qpf)
            self.addValues(RMParser.dataType.WIND, wind)
            self.addValues(RMParser.dataType.CONDITION, condition)

        except:
            log.error("Failed to get simple forecast")


    def __getSolarRadiation(self):
        historyForecast = self.jsonResponse["history"]["observations"]
        if historyForecast is None:
            log.debug("No hourly forecast found for solar radiation")
            return

        arrSR = []
        arrT = []

        for obsdict in historyForecast:
            instantSr = self.__toFloat(obsdict["solarradiation"])
            if instantSr is None:
                log.debug("Invalid solar radiation value found in forecast")
                return
            arrSR.append(instantSr)
            hour = self.__toInt(obsdict["date"]["hour"])
            min = self.__toInt(obsdict["date"]["min"])
            mm = hour*60 + min
            arrT.append(mm)
        #computing solar energy per minute (measurement unit = W*min*m-2)
        solarRadEnergy = 0
        for i in range(0, len(arrSR)):
            dt = arrT[i]
            if(i>0):
                dt -= arrT[i-1]
            solarRadEnergy += dt * arrSR[i]

        #converting to W*h*m-2
        solarRadEnergy = solarRadEnergy / 60
        #converting to MJ*m-2
        solarRadEnergyMJ = solarRadEnergy * 3.6 /1000

        #time utc
        jutc = self.jsonResponse["history"]["utcdate"]
        yyyy = self.__toInt(jutc["year"])
        mm = self.__toInt(jutc["mon"])
        dd = self.__toInt(jutc["mday"])
        hour = self.__toInt(jutc["hour"])
        mins = self.__toInt(jutc["min"])
        dd = datetime.datetime(yyyy, mm, dd, hour, mins)
        timestamp = calendar.timegm( dd.timetuple())
        self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, solarRadEnergyMJ)

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

