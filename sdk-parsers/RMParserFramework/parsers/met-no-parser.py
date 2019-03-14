# Copyright (c) 2014-2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmTypeUtils import *

import datetime, time, os
from xml.etree import ElementTree as e
from datetime import timedelta

from RMDataFramework.rmUserSettings import globalSettings


class METNO(RMParser):
    parserName = "METNO Parser"
    parserDescription = "Global weather service from Norwegian Meteorological Institute http://met.no"
    parserForecast = True
    parserHistorical = False
    parserEnabled = True
    parserDebug = False
    parserInterval = 6 * 3600
    params = {}

    def isEnabledForLocation(self, timezone, lat, long):
        if METNO.parserEnabled and timezone:
            return timezone.startswith("Europe")
        return False

    def perform(self):
        s = self.settings
        URL = "http://api.met.no/weatherapi/locationforecastlts/1.3/"
        URLParams = [("lat", s.location.latitude),
                  ("lon", s.location.longitude),
                  ("msl", int(round(s.location.elevation)))]
        #-----------------------------------------------------------------------------------------------
        #
        # Get hourly data.
        #
        d = self.openURL(URL, URLParams)
        if d is None:
            return

        tree = e.parse(d)
        #tree = e.parse("/home/panic/MET.NO/forecast.xml")

        if tree.getroot().tag == 'error':
            log.error("*** No hourly information found in response!")
            self.lastKnownError = "Error: No hourly information found"

            tree.getroot().clear()
            del tree
            tree = None
        else:
            data = self.__parseXMLData(tree)

            # Free memory
            tree.getroot().clear()
            del tree
            tree = None

            temp        = self.__extractTagData(data, 'temperature')
            mintemp     = self.__extractTagData(data, 'minTemperature')
            maxtemp     = self.__extractTagData(data, 'maxTemperature')
            dewpoint    = self.__extractTagData(data, 'dewpointTemperature')
            wind        = self.__extractTagData(data, 'windSpeed')
            humidity    = self.__extractTagData(data, 'humidity')
            pressure    = self.__extractTagData(data, 'pressure')
            qpf         = self.__extractTagData(data, 'precipitation')
            condition   = self.__extractTagData(data, 'symbol')

            # temp = self.__parseWeatherTag(tree, 'temperature')
            # mintemp = self.__parseWeatherTag(tree, 'minTemperature')
            # maxtemp = self.__parseWeatherTag(tree, 'maxTemperature')
            # dewpoint = self.__parseWeatherTag(tree, 'dewpointTemperature')
            # wind = self.__parseWeatherTag(tree, 'windSpeed')
            # humidity = self.__parseWeatherTag(tree, 'humidity')
            # pressure = self.__parseWeatherTag(tree, 'pressure', 'float')
            # qpf = self.__parseWeatherTag(tree, 'precipitation')
            # condition = self.__parseWeatherTag(tree, 'symbol')

            # tree.getroot().clear()
            # del tree
            # tree = None

            self.addValues(RMParser.dataType.TEMPERATURE, temp)
            self.addValues(RMParser.dataType.MINTEMP, mintemp)
            self.addValues(RMParser.dataType.MAXTEMP, maxtemp)
            self.addValues(RMParser.dataType.DEWPOINT, dewpoint)
            self.addValues(RMParser.dataType.WIND, wind)
            self.addValues(RMParser.dataType.RH, humidity)
            self.addValues(RMParser.dataType.QPF, qpf)
            self.addValues(RMParser.dataType.PRESSURE, pressure)
            self.addValues(RMParser.dataType.CONDITION, condition)

    # Build a python dictionary from the XML data
    def __parseXMLData(self, tree):
        dateFormat = "%Y-%m-%dT%H:%M:%SZ"
        data = {}

        for w in tree.getroot().find('product'):
            for wd in w.find('location'):
                tag = wd.tag

                from_time = w.get('from')
                to_time = w.get('to')

                intervalStartTimestamp = rmTimestampFromDateAsString(from_time, dateFormat) + 1 # 1 second more than hour boundary
                intervalEndTimestamp = rmTimestampFromDateAsString(to_time, dateFormat) - 1 # 1 second less than hour boundary

                day, startTimeStr = from_time.split("T")
                endTimeStr = to_time.split("T")[1]

                if tag not in data:
                    data[tag] = {}

                if day not in data[tag]:
                    data[tag][day] = []

                startHourStr =  startTimeStr.split(":")[0]
                endHourStr = endTimeStr.split(":")[0]

                try:
                    if (tag == 'windDirection'):
                        val = toFloat(wd.get('deg'))
                    elif (tag == 'windSpeed'):
                        val = toFloat(wd.get('mps'))
                    elif (tag == 'symbol'):
                        condition = toInt(wd.get('number'))
                        val = self.conditionConvert(condition)
                    elif (tag == 'cloudiness' or tag == 'fog' or tag == 'lowClouds' or tag == 'mediumClouds' or tag == 'highClouds'):
                        val = toFloat(wd.get('percent'))
                    else:
                        val = toFloat(wd.get('value'))

                    # hPa -> kPa
                    if (tag == 'pressure'):
                        val = val / 10

                except Exception, e:
                    val = None
                    log.debug(e)

                data[tag][day].append({
                    "startHour": startHourStr,
                    "endHour": endHourStr,
                    "start": intervalStartTimestamp,
                    "end": intervalEndTimestamp,
                    "value": val
                })
        return data

    # Extract a tag data with timestamps from our previously built python dictionary
    # Some data is available hourly but precipitation and min/max temperatures are available on 6 hours interval
    # We average the hourly available data to 6 hours interval
    def __extractTagData(self, data, tag):
        result = []
        hoursInterval = 6

        if tag not in data:
            return []

        for day in sorted(data[tag].keys()):
            #log.info(day)
            daySum = 0  # For debugging
            partSum = 0 # For averaging hourly data to 6 hours interval
            hourlyCounter = 0
            intervalCounter = 1

            for interval in data[tag][day]:
                value = interval["value"]
                intervalTime = interval["start"]
                sH = int(interval["startHour"])
                eH = int(interval["endHour"])
                if eH == 0:
                    eH = 24
                duration = eH - sH

                # We found a "hourly" entry that contains temperature, windSpeed, pressure, dew
                # This always start at 1 not at 0
                if duration == 0:
                    #log.info("\t (%s) %s-%s: %s %s" % (duration, sH, eH, tag, value))
                    partSum += value
                    hourlyCounter += 1
                    if sH % hoursInterval == 0 or hourlyCounter > hoursInterval:
                        partSum /=  hourlyCounter
                        daySum += partSum
                        #log.info("%s Hour average %s to %s (%s values)" % (hoursInterval, tag, partSum, hourlyCounter))
                        result.append((intervalTime, partSum)) # Add 6 hours interval value
                        hourlyCounter = 0
                        partSum = 0
                        intervalCounter += 1
                elif duration != hoursInterval:
                    continue
                elif sH % hoursInterval == 0 and eH % hoursInterval == 0:
                    result.append((intervalTime, value)) # Add 6 hours interval value
                    daySum += value
                    #log.info("\t (%s) %s-%s: %s %s" % (duration, sH, eH, tag, value))
                #else:
                #    log.info("\t SKIP (%s) %s-%s: %s %s" % (duration, sH, eH, tag, value))

            if tag != "precipitation":
                # Any remaining partials for 6h averaging for a day
                if partSum > 0 and hourlyCounter > 0:
                    partSum /= hourlyCounter
                    daySum += partSum
                    #log.info("(Partial) %s Hour Average hourly %s to %s (%s values)" % (hoursInterval, tag, partSum, hourlyCounter))
                    result.append((intervalTime, partSum)) # Add 6 hours interval value
                daySum = daySum/intervalCounter

            #log.info("Day Total/AVG (%s)%s %s\n\n" %  (intervalCounter, tag, daySum))
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


if __name__ == "__main__":
    parser = METNO()
    parser.perform()