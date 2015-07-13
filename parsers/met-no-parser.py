# Copyright (c) 2014-2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>
#          Virgil Dinu <virgil.dinu@coretech.ro>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions

import datetime, time
from xml.etree import ElementTree as e
from datetime import timedelta


class METNO(RMParser):
    parserName = "METNO Parser"
    parserEnabled = True
    parserDebug = False
    parserInterval = 21600
    params = {}

    def isEnabledForLocation(self, timezone, lat, long):
        if METNO.parserEnabled and timezone:
            return timezone.startswith("Europe")
        return False

    def perform(self):
        s = self.settings
        URL = "http://api.met.no/weatherapi/locationforecastlts/1.2/"
        URLParams = [("lat", s.location.latitude),
                  ("lon", s.location.longitude)]
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

            tree.getroot().clear()
            del tree
            tree = None
        else:
            temp = self.__parseWeatherTag(tree, 'temperature')
            dewpoint = self.__parseWeatherTag(tree, 'dewpointTemperature')
            wind = self.__parseWeatherTag(tree, 'windSpeed')
            humidity = self.__parseWeatherTag(tree, 'humidity')
            pressure = self.__parseWeatherTag(tree, 'pressure', 'float')
            qpf = self.__parseWeatherTag(tree, 'precipitation')
            condition = self.__parseWeatherTag(tree, 'symbol')

            tree.getroot().clear()
            del tree
            tree = None

            self.addValues(RMParser.dataType.TEMPERATURE, temp)
            self.addValues(RMParser.dataType.DEWPOINT, dewpoint)
            self.addValues(RMParser.dataType.WIND, wind)
            self.addValues(RMParser.dataType.RH, humidity)
            self.addValues(RMParser.dataType.QPF, qpf)
            self.addValues(RMParser.dataType.PRESSURE, pressure)
            self.addValues(RMParser.dataType.CONDITION, condition)

    def __parseDateTime(self, dt, roundToHour = True):
        seconds = int((dt - datetime.datetime.utcfromtimestamp(0)).total_seconds())
        if roundToHour:
            return seconds - (seconds % 3600)
        else:
            return seconds

    def __parseWeatherTag(self, tree, tag, typeConvert = None):
        values = []
        startTimes = []
        lastEndTime = None

        for w in tree.getroot().find('product'):
            for wd in w.find('location'):
                if wd.tag == tag:

                    from_time = w.get('from')
                    to_time = w.get('to')
                    ft = datetime.datetime.strptime(from_time, "%Y-%m-%dT%H:%M:%SZ")
                    tt = datetime.datetime.strptime(to_time, "%Y-%m-%dT%H:%M:%SZ")
                    td = tt - ft

                    shouldSkip = False
                    # skip 6h intervals as they aren't disjoint between them (eg: 0-6, 3-9)
                    # only if we had a previous report with same end time
                    if lastEndTime is not None and lastEndTime == tt and td.seconds == 6 * 3600:
                        shouldSkip = True


                    log.debug("Tag %s [%s - %s] Skip: %s" % (tag, from_time, to_time, shouldSkip))

                    if shouldSkip:
                        continue

                    lastEndTime = tt
                    startTimes.append(self.__parseDateTime(ft))
                    try:
                        if (tag == 'windDirection'):
                            val = wd.get('deg')
                        elif (tag == 'windSpeed'):
                            val = wd.get('mps')
                        elif (tag == 'symbol'):
                            condition = int(wd.get('number'), RMParser.conditionType.Unknown)
                            val = self.conditionConvert(condition)
                        elif (tag == 'cloudiness' or tag == 'fog' or tag == 'lowClouds' or tag == 'mediumClouds' or tag == 'highClouds'):
                            val = wd.get('percent')
                        else:
                            val = wd.get('value')

                        if typeConvert == 'int':
                            val = int(val)
                        if typeConvert == 'float':
                            val = float(val)

                        # hPa -> kPa
                        if (tag == 'pressure'):
                            val = val / 10                            
                    except Exception, e:
                        val = None
                        log.debug(e)
                    values.append(val)

        result = zip(startTimes, values)
        return result


    def conditionConvert(self, symbol):
        if symbol in [999]:
            return RMParser.conditionType.MostlyCloudy
        elif symbol in [1, 101]:
            return RMParser.conditionType.Fair
        elif symbol in [2, 102]:
            return RMParser.conditionType.FewClouds
        elif symbol in [3, 103]:
            return RMParser.conditionType.PartlyCloudy
        elif symbol in [4, 104]:
            return RMParser.conditionType.Overcast
        elif symbol in [15, 115]:
            return  RMParser.conditionType.Fog
        elif symbol in [999]:
            return  RMParser.conditionType.Smoke
        elif symbol in [999]:
            return  RMParser.conditionType.HeavyFreezingRain
        elif symbol in [999]:
            return  RMParser.conditionType.IcePellets
        elif symbol in [999]:
            return  RMParser.conditionType.FreezingRain
        elif symbol in [48, 148]:
            return  RMParser.conditionType.RainIce
        elif symbol in [7, 12, 20, 21, 23, 26, 27, 31, 32, 42, 43, 47, 107, 112, 120, 121, 123, 126, 127, 131, 132, 142, 143, 147]:
            return  RMParser.conditionType.RainSnow
        elif symbol in [10, 25, 41, 110, 125, 141]:
            return  RMParser.conditionType.RainShowers
        elif symbol in [11, 14, 111, 114]:
            return  RMParser.conditionType.Thunderstorm
        elif symbol in [8, 13, 21, 28, 29, 33, 34, 44, 45, 49, 50, 108, 113, 121, 128, 129, 133, 134, 144, 145, 149, 150]:
            return  RMParser.conditionType.Snow
        elif symbol in [999]:
            return  RMParser.conditionType.Windy
        elif symbol in [999]:
            return  RMParser.conditionType.ShowersInVicinity
        elif symbol in [999]:
            return  RMParser.conditionType.HeavyFreezingRain
        elif symbol in [999]:
            return  RMParser.conditionType.ThunderstormInVicinity
        elif symbol in [5, 6, 9, 22, 24, 30, 40, 46, 109, 105, 106, 122, 124, 130, 140, 146]:
            return  RMParser.conditionType.LightRain
        elif symbol in [999]:
            return  RMParser.conditionType.HeavyRain
        elif symbol in [999]:
            return  RMParser.conditionType.FunnelCloud
        elif symbol in [999]:
            return  RMParser.conditionType.Dust
        elif symbol in [999]:
            return  RMParser.conditionType.Haze
        elif symbol in [999]:
            return  RMParser.conditionType.Hot
        elif symbol in [999]:
            return  RMParser.conditionType.Cold
        else:
            return  RMParser.conditionType.Unknown