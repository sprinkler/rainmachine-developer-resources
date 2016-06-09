# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmUtils import convertKnotsToMS, convertFahrenheitToCelsius, convertInchesToMM

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

    def isEnabledForLocation(self, timezone, lat, long):
        if NOAA.parserEnabled and timezone:
            return timezone.startswith("America") or timezone.startswith("US")
        return False

    def perform(self):
        s = self.settings
        URL = "http://graphical.weather.gov/xml/sample_products/browser_interface/ndfdXMLclient.php"
        URLDaily = "http://graphical.weather.gov/xml/sample_products/browser_interface/ndfdBrowserClientByDay.php"
        URLParams = [("lat", s.location.latitude),
                  ("lon", s.location.longitude)] + \
            [
                ("startDate", datetime.date.today().strftime("%Y-%m-%d")),
                #("endDate", (datetime.date.today() + datetime.timedelta(6)).strftime("%Y-%m-%d")),
                ("format", "24 hourly"),
                ("numDays", 6),
                ("Unit", "e")
            ]

        #-----------------------------------------------------------------------------------------------
        #
        # Get hourly data.
        #
        d = self.openURL(URL, URLParams)
        if d is None:
            return

        tree = e.parse(d)

        if tree.getroot().tag == 'error':
            log.error("*** No hourly information found in response!")
            self.lastKnownError = "Error: No hourly information found"
            tree.getroot().clear()
            del tree
            tree = None
        else:
            # We get them in English units need in Metric units
            maxt = self.__parseWeatherTag(tree, 'temperature', 'maximum')
            maxt = convertFahrenheitToCelsius(maxt)

            mint = self.__parseWeatherTag(tree, 'temperature', 'minimum', useStartTimes=False) # for mint we want the end-time to be saved in DB
            mint = convertFahrenheitToCelsius(mint)

            temp = self.__parseWeatherTag(tree, 'temperature', 'hourly')
            temp = convertFahrenheitToCelsius(temp)

            qpf = self.__parseWeatherTag(tree, 'precipitation', 'liquid')
            qpf = convertInchesToMM(qpf)

            dew = self.__parseWeatherTag(tree, 'temperature', 'dew point')
            dew = convertFahrenheitToCelsius(dew)

            wind = self.__parseWeatherTag(tree, 'wind-speed', 'sustained')
            wind = convertKnotsToMS(wind)

            # These are as percentages
            pop = self.__parseWeatherTag(tree, 'probability-of-precipitation', '12 hour')
            humidity = self.__parseWeatherTag(tree, 'humidity', 'relative')
            minHumidity = self.__parseWeatherTag(tree, 'humidity', 'minimum relative')
            maxHumidity = self.__parseWeatherTag(tree, 'humidity', 'maximum relative')

            tree.getroot().clear()
            del tree
            tree = None

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

        #-----------------------------------------------------------------------------------------------
        #
        # Get daily data.
        #
        d = self.openURL(URLDaily, URLParams)
        tree = e.parse(d)

        if tree.getroot().tag == 'error':
            log.error("*** No daily information found in response!")
            self.lastKnownError = "Error: No daily information found"
            tree.getroot().clear()
            del tree
            tree = None
        else:
            conditions = self.__parseWeatherTag(tree, 'conditions-icon', 'forecast-NWS', 'icon-link')
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

        if self.parserDebug:
            log.debug(self.result)

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

    def __parseWeatherTag(self, tree, tag, type, subtag = "value", useStartTimes = True, typeConvert = None):
        values = []
        forecastTimes = []
        timeLayoutKey = None

        tuple = datetime.datetime.fromtimestamp(int(time.time())).timetuple()
        dayTimestamp = int(datetime.datetime(tuple.tm_year, tuple.tm_mon, tuple.tm_mday).strftime("%s"))
        maxDayTimestamp = dayTimestamp + globalSettings.parserDataSizeInDays * 86400

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
        result = [z for z in result if dayTimestamp <= z[0] < maxDayTimestamp]
        return result




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
