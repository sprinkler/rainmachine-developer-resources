# Copyright (c) 2024 RainMachine, Green Electronics LLC
# All rights reserved.

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmGetStartOfDay, rmCurrentDayTimestamp, rmDeltaDayFromTimestamp
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType
import json


class WUndergroundV2(RMParser):
    parserName        = "WUnderground V2 Parser"
    parserDescription = "Global weather service from https://preview.wunderground.com/"
    parserForecast    = True
    parserHistorical  = True
    parserEnabled     = False
    parserDebug       = False
    parserID          = "wundergroundv2"
    parserInterval    = 1 * 3600

    params = {
        "apiKey":                None,
        "stationId":             None,
        "_nearbyStationsIDList": [],
    }

    apiLocationURL   = "https://api.weather.com/v3/location/near"
    apiHistoricalURL = "https://api.weather.com/v2/pws/dailysummary/7day"
    apiForecastURL   = "https://api.weather.com/v3/wx/forecast/daily/5day"

    def isEnabledForLocation(self, timezone, lat, long):
        apiKey    = self.params.get("apiKey")
        stationId = self.params.get("stationId")
        return (WUndergroundV2.parserEnabled
                and isinstance(apiKey, str) and len(apiKey) > 0
                and isinstance(stationId, str) and len(stationId) > 0)

    def perform(self):
        self.params["_nearbyStationsIDList"] = []
        self.lastKnownError = ""

        apiKey    = self.params.get("apiKey")
        stationId = self.params.get("stationId")

        if not isinstance(apiKey, str) or not apiKey:
            self.lastKnownError = "Error: No API Key provided."
            log.error(self.lastKnownError)
            return

        if not isinstance(stationId, str) or not stationId:
            self.lastKnownError = "Error: No Station ID provided."
            log.error(self.lastKnownError)
            return

        self.__getNearbyStations(apiKey)

        hasHistorical = self.__getHistorical(apiKey, stationId)
        hasForecast   = self.__getForecast(apiKey)

        if not hasHistorical and not hasForecast:
            self.lastKnownError = "Error: No data received."
            log.error(self.lastKnownError)
        elif not hasHistorical:
            log.warning("WUndergroundV2: no historical data.")
        elif not hasForecast:
            log.warning("WUndergroundV2: no forecast data.")
        else:
            log.info("WUndergroundV2: historical and forecast data retrieved.")

    def __getNearbyStations(self, apiKey):
        s = self.settings
        URLParams = [
            ("geocode", "%s,%s" % (s.location.latitude, s.location.longitude)),
            ("product", "pws"),
            ("format",  "json"),
            ("apiKey",  str(apiKey)),
        ]
        try:
            d = self.openURL(self.apiLocationURL, URLParams)
            if d is None:
                log.warning("WUndergroundV2: cannot fetch nearby stations.")
                return
            data = json.loads(d.read())
            self.__parseNearbyStations(data)
        except Exception, e:
            log.warning("WUndergroundV2: nearby station lookup failed: %s" % e)

    def __parseNearbyStations(self, data):
        try:
            location   = data["location"]
            stationIds = location.get("stationId", []) or []
            latitudes  = location.get("latitude",  []) or []
            longitudes = location.get("longitude", []) or []
            distances  = location.get("distanceKm", []) or []

            stations = []
            for i, sid in enumerate(stationIds):
                if sid is None:
                    continue
                stations.append({
                    "id":       sid,
                    "lat":      latitudes[i],
                    "lon":      longitudes[i],
                    "distance": distances[i],
                })
            stations.sort(key=lambda x: x["distance"])

            for st in stations:
                self.params["_nearbyStationsIDList"].append(
                    "%s (%.1fkm; lat=%.2f, lon=%.2f)" % (
                        st["id"], st["distance"], st["lat"], st["lon"]))
        except Exception, e:
            log.warning("WUndergroundV2: error parsing nearby stations: %s" % e)

    def __getHistorical(self, apiKey, stationId):
        URLParams = [
            ("stationId", str(stationId)),
            ("format",    "json"),
            ("units",     "m"),
            ("apiKey",    str(apiKey)),
        ]
        try:
            d = self.openURL(self.apiHistoricalURL, URLParams)
            if d is None:
                self.lastKnownError = "Error: Cannot download historical data."
                log.error(self.lastKnownError)
                return False
            data = json.loads(d.read())

            if self.parserDebug:
                with open("wu2-historical-dump.json", "w") as f:
                    json.dump(data, f, indent=2)

            return self.__parseHistorical(data)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get historical data."
            log.error(self.lastKnownError)
            log.exception(e)
            return False

    def __parseHistorical(self, data):
        tsToday     = rmCurrentDayTimestamp()
        tsYesterday = rmDeltaDayFromTimestamp(tsToday, -1)
        limits      = RMWeatherDataLimits()
        hasData     = False

        try:
            for obs in data.get("summaries", []):
                epoch = obs.get("epoch")
                if epoch is None:
                    continue
                tsDay = rmGetStartOfDay(epoch)

                m = obs.get("metric") or {}

                temperature = self.__toFloat(m.get("tempAvg"))
                mintemp     = self.__toFloat(m.get("tempLow"))
                maxtemp     = self.__toFloat(m.get("tempHigh"))
                rh          = self.__toFloat(obs.get("humidityAvg"))
                minrh       = self.__toFloat(obs.get("humidityLow"))
                maxrh       = self.__toFloat(obs.get("humidityHigh"))
                dewpoint    = self.__toFloat(m.get("dewptAvg"))
                wind        = self.__toFloat(m.get("windspeedAvg"))
                rain        = self.__toFloat(m.get("precipTotal"))

                if wind is not None:
                    wind = wind / 3.6  # km/h -> m/s

                maxpressure = self.__toFloat(m.get("pressureMax"))
                minpressure = self.__toFloat(m.get("pressureMin"))
                if maxpressure is not None:
                    maxpressure = limits.sanitize(RMWeatherDataType.PRESSURE, maxpressure / 10.0)
                if minpressure is not None:
                    minpressure = limits.sanitize(RMWeatherDataType.PRESSURE, minpressure / 10.0)
                pressure = None
                if maxpressure is not None and minpressure is not None:
                    pressure = (maxpressure + minpressure) / 2.0

                if tsDay == tsYesterday:
                    solarRaw = self.__toFloat(m.get("solarRadiationHigh"))
                    solar    = solarRaw * 0.0864 if solarRaw is not None else None  # W/m^2 -> MJ/m^2/day (peak reading used as daily proxy)

                    self.addValue(RMParser.dataType.TEMPERATURE,    tsDay, temperature, False)
                    self.addValue(RMParser.dataType.MINTEMP,        tsDay, mintemp,     False)
                    self.addValue(RMParser.dataType.MAXTEMP,        tsDay, maxtemp,     False)
                    self.addValue(RMParser.dataType.RH,             tsDay, rh,          False)
                    self.addValue(RMParser.dataType.MINRH,          tsDay, minrh,       False)
                    self.addValue(RMParser.dataType.MAXRH,          tsDay, maxrh,       False)
                    self.addValue(RMParser.dataType.WIND,           tsDay, wind,        False)
                    self.addValue(RMParser.dataType.RAIN,           tsDay, rain,        False)
                    self.addValue(RMParser.dataType.DEWPOINT,       tsDay, dewpoint,    False)
                    self.addValue(RMParser.dataType.PRESSURE,       tsDay, pressure,    False)
                    self.addValue(RMParser.dataType.SOLARRADIATION, tsDay, solar,       False)
                    hasData = True
                elif tsDay == tsToday:
                    # Today's RAIN only - avoids overwriting forecast data
                    self.addValue(RMParser.dataType.RAIN, tsDay, rain, False)
                    hasData = True

            return hasData
        except Exception, e:
            self.lastKnownError = "Warning: Failed to parse historical data."
            log.error(self.lastKnownError)
            log.exception(e)
            return False

    def __getForecast(self, apiKey):
        s = self.settings
        URLParams = [
            ("geocode",  "%s,%s" % (s.location.latitude, s.location.longitude)),
            ("language", "en-US"),
            ("units",    "m"),
            ("format",   "json"),
            ("apiKey",   str(apiKey)),
        ]
        try:
            d = self.openURL(self.apiForecastURL, URLParams)
            if d is None:
                self.lastKnownError = "Error: Cannot download forecast data."
                log.error(self.lastKnownError)
                return False
            data = json.loads(d.read())

            if self.parserDebug:
                with open("wu2-forecast-dump.json", "w") as f:
                    json.dump(data, f, indent=2)

            self.__parseForecast(data)
            return True
        except Exception, e:
            self.lastKnownError = "Error: Cannot get forecast data."
            log.error(self.lastKnownError)
            log.exception(e)
            return False

    def __parseForecast(self, data):
        daypartList = data.get("daypart") or []
        if not daypartList:
            log.warning("WUndergroundV2: no daypart data in forecast response.")
            return
        dp = daypartList[0]

        arrIconCode     = dp.get("iconCode")             or []
        arrRH           = dp.get("relativeHumidity")     or []
        arrWind         = dp.get("windSpeed")            or []
        arrDewpoint     = dp.get("temperatureDewPoint")  or []
        arrPrecipChance = dp.get("precipChance")         or []
        arrCloudCover   = dp.get("cloudCover")           or []

        arrTS      = data.get("validTimeUtc")   or []
        arrMinTemp = data.get("temperatureMin") or []
        arrMaxTemp = data.get("temperatureMax") or []
        arrQPF     = data.get("qpf")            or []

        for i, ts in enumerate(arrTS):
            mintemp = self.__toFloat(arrMinTemp[i] if i < len(arrMinTemp) else None)
            maxtemp = self.__toFloat(arrMaxTemp[i] if i < len(arrMaxTemp) else None)
            qpf     = self.__toFloat(arrQPF[i]     if i < len(arrQPF)     else None)

            ni = 2 * i      # night part index
            di = 2 * i + 1  # day part index

            minrh = self.__toFloat(arrRH[ni] if ni < len(arrRH) else None)
            maxrh = self.__toFloat(arrRH[di] if di < len(arrRH) else None)

            windNight = self.__toFloat(arrWind[ni] if ni < len(arrWind) else None)
            windDay   = self.__toFloat(arrWind[di] if di < len(arrWind) else None)
            wind = None
            if windNight is not None and windDay is not None:
                wind = (windNight + windDay) / 2.0 / 3.6  # km/h -> m/s
            elif windDay is not None:
                wind = windDay / 3.6
            elif windNight is not None:
                wind = windNight / 3.6

            dewNight = self.__toFloat(arrDewpoint[ni] if ni < len(arrDewpoint) else None)
            dewDay   = self.__toFloat(arrDewpoint[di] if di < len(arrDewpoint) else None)
            dewpoint = None
            if dewNight is not None and dewDay is not None:
                dewpoint = (dewNight + dewDay) / 2.0
            elif dewDay is not None:
                dewpoint = dewDay
            elif dewNight is not None:
                dewpoint = dewNight

            popNight = self.__toFloat(arrPrecipChance[ni] if ni < len(arrPrecipChance) else None)
            popDay   = self.__toFloat(arrPrecipChance[di] if di < len(arrPrecipChance) else None)
            pop = None
            if popNight is not None and popDay is not None:
                pop = max(popNight, popDay)
            elif popDay is not None:
                pop = popDay
            elif popNight is not None:
                pop = popNight

            skyNight = self.__toFloat(arrCloudCover[ni] if ni < len(arrCloudCover) else None)
            skyDay   = self.__toFloat(arrCloudCover[di] if di < len(arrCloudCover) else None)
            skycover = None
            if skyNight is not None and skyDay is not None:
                skycover = (skyNight + skyDay) / 2.0
            elif skyDay is not None:
                skycover = skyDay
            elif skyNight is not None:
                skycover = skyNight

            iconCode  = arrIconCode[ni] if ni < len(arrIconCode) else None
            condition = self.__conditionConvert(iconCode)

            if mintemp   is not None: self.addValue(RMParser.dataType.MINTEMP,   ts, mintemp,   False)
            if maxtemp   is not None: self.addValue(RMParser.dataType.MAXTEMP,   ts, maxtemp,   False)
            if minrh     is not None: self.addValue(RMParser.dataType.MINRH,     ts, minrh,     False)
            if maxrh     is not None: self.addValue(RMParser.dataType.MAXRH,     ts, maxrh,     False)
            if wind      is not None: self.addValue(RMParser.dataType.WIND,      ts, wind,      False)
            if qpf       is not None: self.addValue(RMParser.dataType.QPF,       ts, qpf,       False)
            if condition is not None: self.addValue(RMParser.dataType.CONDITION, ts, condition, False)
            if dewpoint  is not None: self.addValue(RMParser.dataType.DEWPOINT,  ts, dewpoint,  False)
            if pop       is not None: self.addValue(RMParser.dataType.POP,       ts, pop,       False)
            if skycover  is not None: self.addValue(RMParser.dataType.SKYCOVER,  ts, skycover,  False)

    def __conditionConvert(self, iconCode):
        if iconCode is None:
            return None
        if iconCode < 3:
            return RMParser.conditionType.FunnelCloud
        elif iconCode < 5 or iconCode == 38:
            return RMParser.conditionType.Thunderstorm
        elif iconCode in (5, 7, 17, 18):
            return RMParser.conditionType.RainSnow
        elif iconCode == 6:
            return RMParser.conditionType.RainIce
        elif iconCode in (8, 10):
            return RMParser.conditionType.FreezingRain
        elif iconCode in (9, 11, 35):
            return RMParser.conditionType.LightRain
        elif iconCode in (12, 40):
            return RMParser.conditionType.HeavyRain
        elif iconCode in (13, 14, 15, 16, 41, 42, 43, 46):
            return RMParser.conditionType.Snow
        elif iconCode == 20:
            return RMParser.conditionType.Fog
        elif iconCode == 21:
            return RMParser.conditionType.Haze
        elif iconCode == 22:
            return RMParser.conditionType.Smoke
        elif iconCode in (23, 24):
            return RMParser.conditionType.Windy
        elif iconCode == 25:
            return RMParser.conditionType.IcePellets
        elif iconCode == 26:
            return RMParser.conditionType.FewClouds
        elif iconCode in (27, 28):
            return RMParser.conditionType.MostlyCloudy
        elif iconCode in (29, 30):
            return RMParser.conditionType.PartlyCloudy
        elif iconCode in (31, 32, 33, 34, 36):
            return RMParser.conditionType.Fair
        elif iconCode in (37, 47):
            return RMParser.conditionType.ThunderstormInVicinity
        elif iconCode in (39, 45):
            return RMParser.conditionType.RainShowers
        else:
            return RMParser.conditionType.Unknown

    def __toFloat(self, value):
        try:
            if value is None:
                return None
            return float(value)
        except:
            return None


if __name__ == "__main__":
    import os

    class _Location(object):
        latitude  = float(os.environ.get("RM_LAT",       "44.43"))
        longitude = float(os.environ.get("RM_LON",       "26.10"))
        elevation = float(os.environ.get("RM_ELEVATION",  "80.0"))

    class _Settings(object):
        location = _Location()

    p = WUndergroundV2()
    p.parserDebug = True
    p.settings = _Settings()
    p.params["apiKey"]    = os.environ.get("WU_API_KEY",    "")
    p.params["stationId"] = os.environ.get("WU_STATION_ID", "")
    p.perform()

    print "\n--- WU V2 result: %d entries ---" % len(p.result)
    for ts in sorted(p.result):
        print p.result[ts]
    if p.params.get("_nearbyStationsIDList"):
        print "\nNearby stations:"
        for st in p.params["_nearbyStationsIDList"]:
            print "  " + st
