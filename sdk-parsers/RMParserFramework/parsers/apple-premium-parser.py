# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmUtils import convertKmhToMS
from RMDataFramework.rmUserSettings import globalSettings
from urllib2 import URLError
from time import time
import json

class AppleWeatherKit(RMParser):
    parserName = "[Premium] Apple WeatherKit Parser"
    parserDescription = "Global weather service from Apple for RainMachine Premium subscribers"
    parserForecast = True
    parserHistorical = False
    parserID = "applepremium"
    parserInterval = 6 * 3600
    parserEnabled = True
    parserDebug = True

    def perform(self):
        # Albany, NY, USA
        #lat = 42.63
        #lon = -73.76

        lat = globalSettings.location.latitude
        lon = globalSettings.location.longitude

        log.info("Apple Premium WeatherKit perform()")

        self.lastKnownError = ""
        URL = "https://weather.rainmachine.com/appleweather"

        try:
            globalSettings.cloud.readID()
            if not globalSettings.cloud.enabled \
                    or not globalSettings.cloud.sprinklerID \
                    or not globalSettings.cloud.email:
                self.lastKnownError = 'RainMachine Premium not enabled'
                log.error(self.lastKnownError)
                return False
        except Exception, e:
            self.lastKnownError = 'Cannot get RainMachine Premium information'
            log.error(self.lastKnownError)
            return False

        URLParams = [
            ("lat", lat),
            ("lon", lon),
            ("cloudId", globalSettings.cloud.sprinklerID)
        ]

        try:
            conn = self.__openURL(URL, URLParams, globalSettings.cloud.email)
            if conn is None:
                # Don't retry automatically, we don't want to use up user rate limit tokens
                return True
            data = json.loads(conn.read())
            if self.parserDebug:
                log.info(json.dumps(data, indent=4))
            result = self.__parseForecast(data)

            return result
        except Exception, e:
           log.error(e)

        return False


    def __parseForecast(self, forecastDict):
        days = []
        forecastDates = []
        mint = []
        maxt = []
        qpf = []
        conditions = []
        wind = []
        pop = []
        humidity = []
        dateFormat = "%Y-%m-%dT%H:%M:%SZ"
        if "forecastDaily" in forecastDict and "days" in forecastDict["forecastDaily"]:
            days = forecastDict["forecastDaily"]["days"]
            for day in days:
                try:
                    if self.parserDebug:
                        log.info("Day: %s" % day["forecastStart"])

                    # We put both day/overnight time
                    forecastDates.extend([
                        rmTimestampFromUTCDateAsString(day["daytimeForecast"]["forecastStart"], dateFormat),
                        rmTimestampFromUTCDateAsString(day["overnightForecast"]["forecastStart"], dateFormat)
                    ])

                    # Whole day summaries are put twice (due to having both day/overnight time
                    mint.extend([
                        day["temperatureMin"],
                        day["temperatureMin"]
                    ])
                    maxt.extend([
                        day["temperatureMax"],
                        day["temperatureMax"]
                    ])

                    if day["precipitationType"] == "rain":
                        qpf.extend([
                            day["precipitationAmount"],
                            day["precipitationAmount"]
                        ])
                        pop.extend([
                            day["precipitationChance"],
                            day["precipitationChance"]
                        ])
                    else:
                        qpf.extend([None, None])
                        pop.extend([None, None])

                    conditions.extend([
                        self.__conditionConvert(day["daytimeForecast"]["conditionCode"]),
                        self.__conditionConvert(day["overnightForecast"]["conditionCode"])
                    ])

                    log.info(self.__conditionConvert(day["daytimeForecast"]["conditionCode"]))
                    log.info(self.__conditionConvert(day["overnightForecast"]["conditionCode"]))

                    wind.extend([
                        convertKmhToMS(day["daytimeForecast"]["windSpeed"]),
                        convertKmhToMS(day["overnightForecast"]["windSpeed"])
                    ])

                    humidity.extend([
                        self.__humidityConvert(day["daytimeForecast"]["humidity"]),
                        self.__humidityConvert(day["overnightForecast"]["humidity"])
                    ])
                except Exception, e:
                    if not isinstance(e, KeyError):
                        log.error(e)
            try:
                self.addValues(RMParser.dataType.MINTEMP, zip(forecastDates, mint))
                self.addValues(RMParser.dataType.MAXTEMP, zip(forecastDates, maxt))
                self.addValues(RMParser.dataType.CONDITION, zip(forecastDates, conditions))
                self.addValues(RMParser.dataType.QPF, zip(forecastDates, qpf))
                self.addValues(RMParser.dataType.WIND, zip(forecastDates, wind))
                self.addValues(RMParser.dataType.RH, zip(forecastDates, humidity))
                self.addValues(RMParser.dataType.POP, zip(forecastDates, pop))
                return True
            except Exception, e:
                log.error(e)
                self.lastKnownError = 'Cannot parse weather data'

        return False

    def __humidityConvert(self, value):
        try:
            value = float(value) * 100
            return value
        except:
            pass
        return None

    def __conditionConvert(self, conditionStr):
        if 'MostlyCloudy' == conditionStr:
            return RMParser.conditionType.MostlyCloudy
        elif 'Clear' == conditionStr:
            return RMParser.conditionType.Fair
        elif 'MostlyClear' == conditionStr:
            return RMParser.conditionType.FewClouds
        elif 'PartlyCloudy' == conditionStr:
            return RMParser.conditionType.PartlyCloudy
        elif 'Cloudy' == conditionStr:
            return RMParser.conditionType.Overcast
        elif 'Fog' == conditionStr:
            return  RMParser.conditionType.Fog
        elif 'Smoke' == conditionStr:
            return  RMParser.conditionType.Smoke
        elif 'FreezingRain' == conditionStr:
            return  RMParser.conditionType.HeavyFreezingRain
        elif 'MixedRainAndSleet' == conditionStr or 'Hail' == conditionStr:
            return  RMParser.conditionType.IcePellets
        elif 'MixedRainAndSleet' == conditionStr:
            return  RMParser.conditionType.FreezingRain
        elif 'MixedRainAndSnow' == conditionStr:
            return  RMParser.conditionType.RainSnow
        elif 'Rain' == conditionStr:
            return  RMParser.conditionType.RainShowers
        elif 'Thunderstorm' == conditionStr or 'SevereThunderstorm' == conditionStr:
            return  RMParser.conditionType.Thunderstorm
        elif 'Snow' == conditionStr:
            return  RMParser.conditionType.Snow
        elif 'Windy' == conditionStr:
            return  RMParser.conditionType.Windy
        elif 'ScatteredShowers' == conditionStr:
            return  RMParser.conditionType.ShowersInVicinity
        elif 'fzrara' in conditionStr:
            return  RMParser.conditionType.HeavyFreezingRain
        elif 'IsolatedThunderstorms' == conditionStr:
            return  RMParser.conditionType.ThunderstormInVicinity
        elif 'Drizzle' == conditionStr:
            return  RMParser.conditionType.LightRain
        elif 'HeavyRain' == conditionStr:
            return  RMParser.conditionType.HeavyRain
        elif 'Dust' == conditionStr:
            return  RMParser.conditionType.Dust
        elif 'Haze' == conditionStr:
            return  RMParser.conditionType.Haze
        elif 'Hot' == conditionStr:
            return  RMParser.conditionType.Hot
        elif 'Frigid' == conditionStr:
            return  RMParser.conditionType.Cold
        else:
            return  RMParser.conditionType.Unknown

    def __generateJWT(self):
        """
        Generates a JWT token for Apple WeatherKit:
        https://developer.apple.com/documentation/weatherkitrestapi/request_authentication_for_weatherkit_rest_api
        :return:
        JWT Token
        """
        import jwt

        log.info("Apple WeatherKit __generateJWT()")
        if "keyFile" in self.params and not "keyContent" in self.params:
            with open(self.params["keyFile"], "r") as keyFile:
                self.params["keyContent"] = keyFile.read()

        currentTime = int(time())
        expireTime = currentTime + 60 * 60 * 24 * 365

        payload = {
            "iss": self.params["teamId"],
            "iat": currentTime,
            "exp": expireTime,
            "sub": self.params["serviceId"]
        }
        headers = {
            "alg": self.params["tokenAlg"],
            "kid": self.params["keyId"],
            "id": self.params["teamId"] + "." + self.params["serviceId"],
        }

        token = jwt.encode(payload, self.params["keyContent"], algorithm=self.params["tokenAlg"], headers=headers)
        log.info(token)
        return token



    def __openURL(self, url, params, token):
        return self.openURL(url, params, headers = {
            'User-Agent': '(rainmachine.com, tech@rainmachine.com)',
            'Accept': 'application/json',
            'Authorization': "Bearer " + token
        })

if __name__ == "__main__":
    parser = AppleWeatherKit()
    parser.perform()