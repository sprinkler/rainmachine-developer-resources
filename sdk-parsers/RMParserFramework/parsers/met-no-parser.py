# Copyright (c) 2014-2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmTypeUtils import *

import datetime, time, os
import random
from xml.etree import ElementTree as e
from datetime import timedelta
from collections import OrderedDict

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
        headers = [{ "User-Agent": "RainMachine.com v2" },
                   { "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36"}]

        URL = "https://api.met.no/weatherapi/locationforecast/2.0/classic"

        URLParams = [("lat", s.location.latitude),
                     ("lon",  s.location.longitude),
                     ("altitude", int(round(s.location.elevation)))]


        #-----------------------------------------------------------------------------------------------
        #
        # Get hourly data.
        #
        d = self.openURL(URL, URLParams, headers=headers[random.randint(0, 1)])
        if d is None:
            return

        tree = e.parse(d)
        #tree = e.parse("/tmp/MET.NO/forecast.xml")

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
        todayTimestamp = rmCurrentDayTimestamp()

        for w in tree.getroot().find('product'):
            for wd in w.find('location'):
                tag = wd.tag

                # Reduce memory size by skipping tags that we don't need
                if (tag == 'cloudiness' or tag == 'fog' or tag == 'lowClouds' or tag == 'mediumClouds' or tag == 'highClouds' or tag == 'windDirection'):
                    continue

                from_time = w.get('from')
                to_time = w.get('to')

                # New function call in next branch
                intervalStartTimestamp = rmTimestampFromUTCDateAsString(from_time, dateFormat)
                intervalEndTimestamp = rmTimestampFromUTCDateAsString(to_time, dateFormat)

                if intervalStartTimestamp < todayTimestamp:
                    self.logtrace("From: %s To: %s" % (from_time, to_time))
                    self.logtrace("*** Local conversion of start timestamp (%s) in the past skipping ..." % from_time)
                    continue

                localStartDate = rmTimestampToDate(intervalStartTimestamp)
                localEndDate = rmTimestampToDate(intervalEndTimestamp)

                day = localStartDate.strftime('%Y-%m-%d')

                if tag not in data:
                    data[tag] = OrderedDict()

                if day not in data[tag]:
                    data[tag][day] = []

                startHour = localStartDate.hour
                endHour = localEndDate.hour

                try:
                    val = None
                    if (tag == 'windSpeed'):
                        val = toFloat(wd.get('mps'))
                    elif (tag == 'symbol'):
                        condition = toInt(wd.get('number'))
                        val = self.conditionConvert(condition)
                    elif (tag == 'cloudiness' or tag == 'fog' or tag == 'lowClouds' or tag == 'mediumClouds' or tag == 'highClouds'): # UNUSED
                        val = toFloat(wd.get('percent'))
                    elif (tag == 'windDirection'): # UNUSED
                        val = toFloat(wd.get('deg'))
                    else:
                        val = toFloat(wd.get('value'))

                    # hPa -> kPa
                    if (tag == 'pressure'):
                        val = val / 10

                except Exception, e:
                    val = None
                    log.debug(e)

                data[tag][day].append({
                    "startHour": startHour,
                    "endHour": endHour,
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

        for day in data[tag].keys():
            self.logtrace("Day: %s - %s" % (day, tag))
            daySum = 0  # For debugging
            partSum = None  # For averaging hourly data to 6 hours interval
            hourlyCounter = 0
            intervalCounter = 1
            usedIntervals = []  # Keep track of intervals so we can eliminate intersecting ones

            for interval in data[tag][day]:
                value = interval["value"]
                intervalTime = interval["start"]
                sH = interval["startHour"]
                eH = interval["endHour"]
                shouldSkip = False

                # Ends in next day
                if eH < sH:
                    log.debug("\t (SKIP) Interval %s %s ends in next day" % (sH, eH))
                    continue

                # Does this new interval intersects with an interval already in our data
                for si in usedIntervals:
                    # if tag == "precipitation":
                    #     log.info("Checking %s-%s against %s-%s" % (sH, eH, si[0], si[1]))
                    if sH < si[1]:
                        if tag == "precipitation":
                            log.debug("%s %s" % (day, tag))
                            log.debug("\t (SKIP i) Interval %s-%s intersects with interval %s-%s" % (sH, eH, si[0], si[1]))
                        shouldSkip = True
                        break

                if shouldSkip:
                    continue
                duration = eH - sH

                # We found a "hourly" entry that contains temperature, windSpeed, pressure, dew
                if duration == 0 and value is not None:
                    self.logtrace("\t (%s) %s-%s: %s %s" % (duration, sH, eH, tag, value))
                    if partSum is None:
                        partSum = value
                    else:
                        partSum += value

                    hourlyCounter += 1
                    if sH > 0 and sH % hoursInterval == 0 or hourlyCounter > hoursInterval:
                        partSum /= hourlyCounter
                        daySum += partSum
                        self.logtrace("%s Hour average %s to %s (%s values)" % (hoursInterval, tag, partSum, hourlyCounter))
                        usedIntervals.append((sH, eH))
                        result.append((intervalTime, partSum)) # Add 6 hours interval value
                        hourlyCounter = 0
                        partSum = 0
                        intervalCounter += 1
                elif duration == hoursInterval:
                    usedIntervals.append((sH, eH))
                    result.append((intervalTime, value)) # Add 6 hours interval value
                    daySum += value
                    log.debug("\t ADDED (%s) %s-%s: %s %s" % (duration, sH, eH, tag, value))
                else:
                    log.debug("\t SKIP (%s) %s-%s: %s %s" % (duration, sH, eH, tag, value))

            if tag != "precipitation":
                # Any remaining partials for 6h averaging for a day
                if partSum is not None and hourlyCounter > 0:
                    partSum /= hourlyCounter
                    daySum += partSum
                    self.logtrace("(Partial) %s Hour Average hourly %s to %s (%s values)" % (hoursInterval, tag, partSum, hourlyCounter))
                    usedIntervals.append((sH, eH))
                    result.append((intervalTime, partSum)) # Add 6 hours interval value
                daySum = daySum/intervalCounter

            self.logtrace("Day %s Total/AVG (%s/%s) %s %s (%s)\n\n" %  (day, intervalCounter, hourlyCounter, tag, partSum, daySum))
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

    def logtrace(self, msg, *args, **kwargs):
        if self.parserDebug:
            log.info(msg, *args, **kwargs)

if __name__ == "__main__":
    parser = METNO()
    parser.perform()