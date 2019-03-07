# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Adapted from the WUnderground parser which became deprecated on March 22, 2019
# This parser uses the API that Weather.com has provided for the use of PWS contributors
# Copyright (c) 2019 Gordon Larsen <gordon@the-larsens.ca>
#
# Original Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>
#

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmNowDateTime, rmGetStartOfDay
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
from RMDataFramework.rmUserSettings import globalSettings
import json, time
import datetime, calendar


class WeathercomPWS(RMParser):
    parserName = "Weather.com PWS Parser"
    parserDescription = "Global weather service with personal weather station access from Weather.com (formerly WUnderground)"
    parserForecast = True
    parserHistorical = True
    parserEnabled = True
    parserDebug = False
    parserInterval = 6 * 3600

    params = {"apiKey": "be87c577f9414a3987c577f9413a3917"
        , "pwsStationName": "IBRITISH376"
        }
    apiURL = None
    jsonResponse = None

    def isEnabledForLocation(self, timezone, lat, long):
        return WeathercomPWS.parserEnabled

    def perform(self):
        timeNow = rmNowDateTime()
        timeYesterday = rmNowDateTime().fromordinal(timeNow.toordinal() - 1)
        yyyyy = timeYesterday.year
        mmy = timeYesterday.month
        ddy = timeYesterday.day
        yyyy = timeNow.year
        mm = timeNow.month
        dd = timeNow.day
        ddystr = str(ddy).zfill(2)
        mmystr = str(mmy).zfill(2)
        yyyyystr = str(yyyyy)

        self.lastKnownError = ""
        apiKey = self.params.get("apiKey", None)
        if apiKey is None or not apiKey or not isinstance(apiKey, str):
            log.error("No API Key provided")
            self.lastKnownError = "Error: No API Key provided"
            return

        pwsStationName = self.params.get("pwsStationName", None)
        if pwsStationName is None or not pwsStationName or not isinstance(pwsStationName, str):
            log.error("No PWS Station Name provided")
            self.lastKnownError = "Error: No PWS Name provided"
            return

        #self.apiURL = "https://api.weather.com/v2/pws/dailysummary/7day?stationId=" + pwsStationName + "&format=json&units=m&apiKey=" + str(apiKey)
        #get yesterday's observations
        self.apiURL = "https://api.weather.com/v2/pws/history/daily?stationId=" + pwsStationName + "&format=json&units=m&date="+ yyyyystr + mmystr + ddystr + "&apiKey=" + str(apiKey)
        #get current observations
        #self.apiURL = "https://api.weather.com/v2/pws/observations/current?stationId=" + pwsStationName + "&format=json&units=m&apiKey=" + str(apiKey)

        success = False
        if self.params.get("pwsStationName"):
            stationName = self.params.get("pwsStationName")
            if (stationName is None or not stationName or not isinstance(stationName, str)):
                log.error("Station ID cannot be empty")
                self.lastKnownError = "Error: Station ID cannot be empty"
                return
            log.debug("getting data from specified station")
            # try to split

        self.csapiURL = self.apiURL  # url for pws
        d = self.openURL(self.csapiURL)
        jsonContent = d.read()
        #log.debug(str(jsonContent))

        if jsonContent is None:
            self.lastKnownError = "Error: Bad response"
            self.jsonResponse = json.loads(jsonContent)
            log.debug(str(self.jsonResponse))
            err = self.jsonResponse.get("response").get("error")
            if not err:
                success = True
            else:
                self.lastKnownError = "Error: Failed to get custom station"
                log.error(self.lastKnownError)
        else:
            self.jsonResponse = json.loads(jsonContent)
            #err = self.jsonResponse.get("response").get("error")
            #if not err:
            success = True

        if not success:
            log.error(self.lastKnownError)
            return

        #log.debug(str(self.jsonResponse))
        geoCode = self.getStationData(self.jsonResponse)
        llat = geoCode["llat"]
        llon = geoCode["llon"]
        log.debug("Station Lat: " + str(llat) + " Lon: " + str(llon))

    #get 5day forecast data from new PWS only Weather API using geocode version
        self.apiURL= "https://api.weather.com/v3/wx/forecast/daily/5day?geocode=" + str(llat) + "," + str(llon) + "&format=json&units=m&language=en-CA&apiKey=" + str(apiKey)

        self.csapiURL = self.apiURL  # url for pws
        d = self.openURL(self.csapiURL)
        jsonContent = d.read()
        #log.debug(jsonContent)
        self.jsonResponse = json.loads(jsonContent)

        self.getSimpleForecast(self.jsonResponse)

        return

    def getStationData(self, jsonData):
        # daily summary for yesterday
        #log.debug(str(jsonData))
        try:
            llat = jsonData["observations"][0]["lat"]
            llon = jsonData["observations"][0]["lon"]
            dailysummary = jsonData["observations"][0]["metric"]
            temperature = self.__toFloat(dailysummary["tempAvg"])
            mintemp = self.__toFloat(dailysummary["tempLow"])
            maxtemp = self.__toFloat(dailysummary["tempHigh"])
            rh = self.__toFloat(jsonData["observations"][0]["humidityAvg"])
            minrh = self.__toFloat(jsonData["observations"][0]["humidityLow"])
            maxrh = self.__toFloat(jsonData["observations"][0]["humidityHigh"])
            dewpoint = self.__toFloat(dailysummary["dewptAvg"])
            wind = self.__toFloat(dailysummary["windspeedAvg"])
            if wind is not None:
                wind = wind / 3.6  # converted from kmetersph to mps
            maxpressure = self.__toFloat(dailysummary["pressureMax"])
            minpressure = self.__toFloat(dailysummary["pressureMin"])
            pressure = None
            if maxpressure is not None and minpressure is not None:
                pressure = (maxpressure / 2 + minpressure / 2) / 10  # converted to from mb to kpa

            rain = self.__toFloat(dailysummary["precipTotal"])

            # time utc
            jutc = jsonData["observations"][0]["obsTimeUtc"]
            yyyy = self.__toInt(jutc[:4])
            mm = self.__toInt(jutc[5:7])
            dd = self.__toInt(jutc[8:10])
            hour = self.__toInt(jutc[11:13])
            mins = self.__toInt(jutc[14:16])
            log.debug("Observations for date: %d/%d/%d Temp: %s, Rain: %s" % (yyyy, mm, dd, temperature, rain))

            dd = datetime.datetime(yyyy, mm, dd, hour, mins)
            timestamp = calendar.timegm(dd.timetuple())
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

        return {'llat':llat, 'llon':llon} # return lat and long of PWS to acquire forecast

    def getSimpleForecast(self, jsonResponse): #get the 5-day forecast
        try:
            tuple = datetime.datetime.fromtimestamp(int(time.time())).timetuple()
            dayTimestamp = int(datetime.datetime(tuple.tm_year, tuple.tm_mon, tuple.tm_mday).strftime("%s"))
            maxDayTimestamp = dayTimestamp + globalSettings.parserDataSizeInDays * 86400

            timestamp = []
            temperatureMax = []
            temperatureMin = []
            wind = []
            humidity = []
            qpf = []
            condition = []

            for i in range(5):
                tt = self.__toInt(jsonResponse["validTimeUtc"][i])
                tt = rmGetStartOfDay(self.__toFloat(tt))
                if tt > maxDayTimestamp:
                    break
                timestamp.append(self.__toInt(tt))
                temperatureMax.append(self.__toFloat(jsonResponse["temperatureMax"][i]))
                temperatureMin.append(self.__toFloat(jsonResponse["temperatureMin"][i]))
                qpf.append(self.__toFloat(jsonResponse["qpf"][i]))

            for i in range(0, 10, 2):
                windValueDay = self.__toFloat(jsonResponse["daypart"][0]["windSpeed"][i])
                windValueNight = self.__toFloat(jsonResponse["daypart"][0]["windSpeed"][i+1])
                windValue = (windValueDay + windValueNight) / 2
                windValue = self.__toFloat(windValue)
                if windValue is not None:
                    wind.append(windValue / 3.6)  # convertred from kmetersph to meterps

                humidityDay = self.__toFloat(jsonResponse["daypart"][0]["relativeHumidity"][i])
                humidityNight = self.__toFloat(jsonResponse["daypart"][0]["relativeHumidity"][i + 1])
                humidity.append((humidityDay + humidityNight) /2) #Average the day and night forecast
                condition.append(self.conditionConvert(jsonResponse["daypart"][0]["wxPhraseLong"][i])) #take only the first condition statement

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

        except
            log.error("Failed to get simple forecast")


    def __parseDateTime(self, timestamp, roundToHour=True):
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
        elif 'Funnel Cloud' in conditionStr:
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
        # type: (object) -> object
        try:
            if value is None:
                return value
            return int(value)
        except:
            return None


#if __name__ == "__main__":
#    log.info("WeathercomPWS parser running")
#    p = WeathercomPWS()
#    p.perform()
