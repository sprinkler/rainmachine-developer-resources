# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmUtils import convertKnotsToMS, convertFahrenheitToCelsius, convertInchesToMM, convertToFloat, convertToInt
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType

import datetime, time
from xml.etree import ElementTree as e


class NOAA(RMParser):
    parserName = "NOAA Parser"
    parserDescription = "North America weather forecast from National Oceanic and Atmospheric Administration"
    parserForecast = True
    parserHistorical = False
    parserEnabled = True
    parserDebug = False
    parserInterval = 6 * 3600
    params = {}

    skippedDays = {} # keep track of incomplete days
    intervalsCache = {} # keep track of intervals in the current day

    def isEnabledForLocation(self, timezone, lat, long):
        if NOAA.parserEnabled and timezone:
            return timezone.startswith("America") or timezone.startswith("US")
        return False

    def perform(self):
        s = self.settings

        # Order is important
        urls = [
            {
                "host": "https://noaa.rainmachine.com",
                "headers": {"Host": "graphical.weather.gov"},
                "params": []
            },
            {
                "host": "https://noaa.rainmachine.com",
                "headers": {"Host": "graphical.weather.gov"},
                "params": []
            },
            {
                "host": "https://forecast.rainmachine.com",
                "headers": {},
                "params": [("token", "px808345forc")]
            },
            {
                "host": "https://graphical.weather.gov",
                "headers": {},
                "params": []
            },
        ]

        hourlyPath = "/xml/sample_products/browser_interface/ndfdXMLclient.php"
        dailyPath = "/xml/sample_products/browser_interface/ndfdBrowserClientByDay.php"

        baseParams = [
           ("lat", s.location.latitude),
           ("lon", s.location.longitude)
        ]

        # baseParams = [
        #    ("lat", "27"),
        #    ("lon", "-80")
        # ]

        hourlyParams = [
            ("product", "time-series"),
            ("begin", datetime.date.today().strftime("%Y-%m-%d")),
            ("Unit", "e"),
            ("maxt", "maxt"),
            ("mint", "mint"),
            ("temp", "temp"),
            ("qpf", "qpf"),
            ("dew", "dew"),
            ("pop12", "pop12"),
            ("wspd", "wspd"),
            ("rh", "rh"),
            ("maxrh", "maxrh"),
            ("minrh", "minrh")
        ]

        dailyParams = [
            ("startDate", datetime.date.today().strftime("%Y-%m-%d")),
            #("endDate", (datetime.date.today() + datetime.timedelta(6)).strftime("%Y-%m-%d")),
            ("format", "24 hourly"),
            ("numDays", 6),
            ("Unit", "e")
        ]

        baseHeaders = {"User-Agent": "RainMachine v2"}

        hasHourly = False
        hasDaily = False

        for url in urls:
            hourlyURL = url["host"] + hourlyPath
            dailyUrl = url["host"] + dailyPath
            urlHourlyParams = baseParams + hourlyParams + url["params"]
            urlDailyParams = baseParams + dailyParams + url["params"]
            url["headers"].update(baseHeaders)

            if not hasHourly:
                log.info("Fetching Hourly data from %s" % hourlyURL)
                hasHourly = self.getHourlyData(hourlyURL, urlHourlyParams, url["headers"])

            if not hasDaily:
                log.info("Fetching Daily data from %s " % dailyUrl)
                hasDaily = self.getDailyData(dailyUrl, urlDailyParams, url["headers"])

            if hasHourly and hasDaily:
                break

        # If we didn't get Hourly data we consider a fail and retry the whole parser operation.
        # We remove any values obtained by daily call so we can trigger parser retry
        if not hasHourly:
            self.clearValues()

        if self.parserDebug:
            log.debug(self.result)

        self.skippedDays = {}

        # Dump existing cache for today
        if self.parserDebug:
            todayTimestamp = rmCurrentDayTimestamp()
            for cacheKey in self.intervalsCache:
                log.info("%s CACHED %s:" % (rmTimestampToDateAsString(todayTimestamp), cacheKey))
                if todayTimestamp in self.intervalsCache[cacheKey]:
                    for entry in self.intervalsCache[cacheKey][todayTimestamp]:
                        v = self.intervalsCache[cacheKey][todayTimestamp][entry]
                        log.info("\t %s: %s" % (rmTimestampToDateAsString(entry), v))


    #-----------------------------------------------------------------------------------------------
    #
    # Get hourly data.
    #
    def getHourlyData(self, URL, URLParams, headers):

        d = self.openURL(URL, URLParams, headers=headers)
        if d is None:
            return False
        try:
            tree = e.parse(d)
        except:
            return False

        #tree = e.parse("/tmp/noaa-fl-2019-06-04-1.xml")

        if tree.getroot().tag == 'error':
            log.error("*** No hourly information found in response!")
            self.lastKnownError = "Retrying hourly data retrieval"
            tree.getroot().clear()
            del tree
            tree = None
            return False

        # Reset lastKnownError from a previous function call
        self.lastKnownError = ""

        # We get them in English units need in Metric units

        # 2019-06-01: If we send that weather properties we want (qpf=qpf&mint=mint) in request URL NOAA response forgets
        # past hours in current day resulting in a forecast requested at the end of the day
        # having null/0 qpf forgetting the older values which could had more qpf so we need to process QPF first and
        # determine which entries don't have full days with qpf reported (especially current day) then completely skip
        # this day for the rest of the weather properties so we don't have a forecast entry with null/0 qpf

        # Algorithm allows multiple partial days to be skipped because incomplete but we currently only skip today

        # QPF needs to be the first tag parsed to build the skippedDays structure
        qpf = self.__parseWeatherTag(tree, 'precipitation', 'liquid', skippedDays=self.skippedDays, addToSkippedDays=True)
        qpf = convertInchesToMM(qpf)

        maxt = self.__parseWeatherTag(tree, 'temperature', 'maximum', skippedDays=self.skippedDays)
        maxt = convertFahrenheitToCelsius(maxt)

        mint = self.__parseWeatherTag(tree, 'temperature', 'minimum', useStartTimes=False, skippedDays=self.skippedDays) # for mint we want the end-time to be saved in DB
        mint = convertFahrenheitToCelsius(mint)

        temp = self.__parseWeatherTag(tree, 'temperature', 'hourly', skippedDays=self.skippedDays)
        temp = convertFahrenheitToCelsius(temp)

        dew = self.__parseWeatherTag(tree, 'temperature', 'dew point', skippedDays=self.skippedDays)
        dew = convertFahrenheitToCelsius(dew)

        wind = self.__parseWeatherTag(tree, 'wind-speed', 'sustained', skippedDays=self.skippedDays)
        wind = convertKnotsToMS(wind)

        # These are as percentages
        pop = self.__parseWeatherTag(tree, 'probability-of-precipitation', '12 hour', skippedDays=self.skippedDays)
        pop = convertToInt(pop)

        humidity = self.__parseWeatherTag(tree, 'humidity', 'relative', skippedDays=self.skippedDays)
        humidity = convertToFloat(humidity)

        minHumidity = self.__parseWeatherTag(tree, 'humidity', 'minimum relative', skippedDays=self.skippedDays)
        minHumidity = convertToFloat(minHumidity)

        maxHumidity = self.__parseWeatherTag(tree, 'humidity', 'maximum relative', skippedDays=self.skippedDays)
        maxHumidity = convertToFloat(maxHumidity)

        if self.parserDebug:
            tree.write('noaa-' + str(rmTimestampToDateAsString(rmCurrentTimestamp())) + ".xml")

        tree.getroot().clear()
        del tree
        tree = None

        # Save
        self.addValues(RMParser.dataType.MINTEMP, mint)
        self.addValues(RMParser.dataType.MAXTEMP, maxt)
        self.addValues(RMParser.dataType.TEMPERATURE, temp)
        self.addValues(RMParser.dataType.QPF, qpf)
        self.addValues(RMParser.dataType.DEWPOINT, dew)
        self.addValues(RMParser.dataType.WIND, wind)
        self.addValues(RMParser.dataType.POP, pop)
        self.addValues(RMParser.dataType.RH, humidity)
        self.addValues(RMParser.dataType.MINRH, minHumidity)
        self.addValues(RMParser.dataType.MAXRH, maxHumidity)

        return True

    #-----------------------------------------------------------------------------------------------
    #
    # Get daily data.
    #
    def getDailyData(self, URLDaily, URLParams, headers):
        d = self.openURL(URLDaily, URLParams, headers=headers)
        try:
            tree = e.parse(d)
        except:
            return False

        if tree.getroot().tag == 'error':
            log.error("*** No daily information found in response!")
            self.lastKnownError = "Retrying daily brief"
            tree.getroot().clear()
            del tree
            tree = None
            return False

        #tree = e.parse("/tmp/noaa-fl-2019-06-04-daily-1.xml")

        # Reset lastKnownError from a previous function call
        self.lastKnownError = ""

        conditions = self.__parseWeatherTag(tree, 'conditions-icon', 'forecast-NWS', 'icon-link', skippedDays=self.skippedDays)
        parsedConditions = []

        for c in conditions:
            if c and len(c) >= 2:
                try:
                    cv = self.conditionConvert(c[1].rsplit('.')[-2].rsplit('/')[-1])
                except:
                    cv = RMWeatherConditions.Unknown

                parsedConditions.append((c[0], cv))

        tree.getroot().clear()
        del tree
        tree = None

        self.addValues(RMParser.dataType.CONDITION, parsedConditions)

        return True


    def __parseDateTime(self, str, roundToHour = True):
        #NOAA reports in location local time needs UTC conversion
        timestamp = rmTimestampFromDateAsStringWithOffset(str)
        if timestamp is None:
            return None

        if roundToHour:
            return timestamp - (timestamp % 3600)
        else:
            return timestamp

    def __parseTimeLayout(self, tree, key, useStartTimes = True):
        found = False
        validDates = []

        # We can index by using "start-valid-time" or by "end-valid-time"
        if useStartTimes:
            dateTagName =  "start-valid-time"
        else:
            dateTagName =  "end-valid-time"

        for timeElement in tree.getroot().getiterator(tag = "time-layout"):
            for timeData in timeElement.getchildren():
                if timeData.tag == "layout-key" and timeData.text == key:
                    found = True
                elif timeData.tag == dateTagName and found:
                    validDates.append(self.__parseDateTime(timeData.text))

            if found:
                break


        return validDates

    # skippedDays will hold the days skipped by other entries (qpf, temp).
    def __parseWeatherTag(self, tree, tag, type, subtag = "value", useStartTimes = True, typeConvert = None, skippedDays = {}, addToSkippedDays = False):
        values = []
        forecastTimes = []
        timeLayoutKey = None
        cacheKey = tag + type

        todayTimestamp = rmCurrentDayTimestamp()
        maxDayTimestamp = todayTimestamp + globalSettings.parserDataSizeInDays * 86400

        # We start a new current day
        if cacheKey not in self.intervalsCache or todayTimestamp not in self.intervalsCache[cacheKey]:
            self.intervalsCache[cacheKey] = {} # forget older days
            self.intervalsCache[cacheKey][todayTimestamp] = {}

        # Build forecast time intervals list and values list
        for w in tree.getroot().getiterator(tag = tag):
            if w.attrib['type'] != type:
                continue

            timeLayoutKey = w.attrib['time-layout']
            forecastTimes = self.__parseTimeLayout(tree, timeLayoutKey, useStartTimes=useStartTimes)

            for wval in w.getiterator(tag = subtag):
                try:
                    val = wval.text
                    if typeConvert == 'int':
                        val = int(val)
                    if typeConvert == 'float':
                        val = float(val)
                except:
                    val = None

                values.append(val)

        result = zip(forecastTimes, values)
        result.sort(key=lambda z: z[0]) # Sort by timestamp

        # If we don't have 'precipitation' for a full 'today' skip all weather properties for today unless we have something cached
        # Otherwise allow partial day weather properties to be saved even if we don't have a cache of them
        # In other words: If we have full 'today' precipitation allow other partial entries if not forget entire day
        tmpresult = []
        lastDay = None
        skipDay = None

        for z in result:
            day = rmGetStartOfDay(z[0])
            if day in skippedDays:
                log.debug("%s %s day %s in skippedDays skipping" % (tag, type, rmTimestampToDateAsString(day)))
                continue

            startDate = rmTimestampToDate(z[0])
            startHour = startDate.hour

            if todayTimestamp > z[0]:
                log.info("%s %s: reject date %s as it's in the past" % (tag, type, rmTimestampToDateAsString(z[0])))
                continue

            if z[0] >= maxDayTimestamp:
                log.debug("%s %s: reject date %s as it's over the max parser day: %s" % (tag, type, rmTimestampToDateAsString(z[0]), rmTimestampToDateAsString(maxDayTimestamp)))
                continue

            # Check for incomplete days
            if lastDay is None or lastDay < day:
                skipDay = None
                lastDay = day
                log.debug("%s %s: found new day: %s - %s" % (tag, type, rmTimestampToDateAsString(day), rmTimestampToDateAsString(lastDay)))
                # Is this a day with partial data not starting at the beginning of day ?
                if startHour > 10:
                    if day == todayTimestamp: # Limit to today
                        if not self.intervalsCache[cacheKey][todayTimestamp]: # Only if no cache
                            skipDay = day

            # Build skippedDays list
            # Save to skipped days so we can skip for all other weather propeties that will be parsed after
            if day == skipDay:
                # Allow adding partial entries if they aren't already in skippedDays for entries have addToSkippedDays = False
                if addToSkippedDays:
                    skippedDays[skipDay] = True
                    log.info("\t%s %s day: %s starting with hour %s (local) skipping with addToSkippedDays..." % (tag, type, rmTimestampToDateAsString(day), startHour))
                    continue

            # Cache: Update with new value. Older intervals that aren't in current result have their cached values
            if day == todayTimestamp:
                self.intervalsCache[cacheKey][todayTimestamp][z[0]] = z[1]
                log.debug("%s Added interval head %s cache with value: %s" % (cacheKey, rmTimestampToDateAsString(z[0]), z[1]))

            if self.parserDebug:
                log.info("Adding %s: %s for %s" % (cacheKey, z[1], rmTimestampToDateAsString(z[0])))
            tmpresult.append(z)


        # Cache: Add cache entries that don't exist to the tmpresult
        # This way we will still have in latest forecastID the data that was retrieved by other parsers runs
        # on this day
        for entry in self.intervalsCache[cacheKey][todayTimestamp]:
            alreadyIn = False
            for z in tmpresult:
                if entry == z[0]:
                    alreadyIn = True
                    break
            if not alreadyIn:
                v = self.intervalsCache[cacheKey][todayTimestamp][entry]
                log.debug("Adding from Cache: %s: %s for %s" % (cacheKey, v, rmTimestampToDateAsString(entry)))
                tmpresult.append((entry, v))

        return tmpresult


    def conditionConvert(self, conditionStr):
        if 'bkn' in conditionStr:
            return RMParser.conditionType.MostlyCloudy
        elif 'skc' in conditionStr:
            return RMParser.conditionType.Fair
        elif 'few' in conditionStr:
            return RMParser.conditionType.FewClouds
        elif 'sct' in conditionStr:
            return RMParser.conditionType.PartlyCloudy
        elif 'ovc' in conditionStr:
            return RMParser.conditionType.Overcast
        elif 'fg' in conditionStr:
            return  RMParser.conditionType.Fog
        elif 'smoke' in conditionStr:
            return  RMParser.conditionType.Smoke
        elif 'fzra' in conditionStr:
            return  RMParser.conditionType.HeavyFreezingRain
        elif 'ip' in conditionStr:
            return  RMParser.conditionType.IcePellets
        elif 'mix' in conditionStr:
            return  RMParser.conditionType.FreezingRain
        elif 'raip' in conditionStr:
            return  RMParser.conditionType.RainIce
        elif 'rasn' in conditionStr:
            return  RMParser.conditionType.RainSnow
        elif 'shra' in conditionStr:
            return  RMParser.conditionType.RainShowers
        elif 'tsra' in conditionStr:
            return  RMParser.conditionType.Thunderstorm
        elif 'sn' in conditionStr:
            return  RMParser.conditionType.Snow
        elif 'wind' in conditionStr:
            return  RMParser.conditionType.Windy
        elif 'shwrs' in conditionStr:
            return  RMParser.conditionType.ShowersInVicinity
        elif 'fzrara' in conditionStr:
            return  RMParser.conditionType.HeavyFreezingRain
        elif 'hi_tsra' in conditionStr:
            return  RMParser.conditionType.ThunderstormInVicinity
        elif 'ra1' in conditionStr:
            return  RMParser.conditionType.LightRain
        elif 'ra' in conditionStr:
            return  RMParser.conditionType.HeavyRain
        elif 'nsvrtsra' in conditionStr:
            return  RMParser.conditionType.FunnelCloud
        elif 'dust' in conditionStr:
            return  RMParser.conditionType.Dust
        elif 'mist' in conditionStr:
            return  RMParser.conditionType.Haze
        elif 'hot' in conditionStr:
            return  RMParser.conditionType.Hot
        elif 'cold' in conditionStr:
            return  RMParser.conditionType.Cold
        else:
            return  RMParser.conditionType.Unknown


if __name__ == "__main__":
    parser = NOAA()
    parser.perform()