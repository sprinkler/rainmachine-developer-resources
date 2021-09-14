# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
from collections import OrderedDict

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmUtils import \
    convertKnotsToMS, \
    convertFahrenheitToCelsius, \
    convertInchesToMM, \
    convertMPHToMS, \
    convertMilesToKM, \
    convertToFloat, \
    convertToInt, \
    distanceBetweenGeographicCoordinatesAsKm

from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType

import datetime, time
from xml.etree import ElementTree as ET


class CWOPKeys:
    # Used for nearby station api call (multiple stations with last recorded observation)
    RAIN = 'rain midnight'
    TEMP = 'temp'
    RH = 'humidity'
    WIND = 'speed'
    PRESSURE = 'barometer'
    DISTANCE = 'distance'
    LAST_SEEN = 'age'
    NAME = 'call'

    # Used for whole day api call (single station all recorded observations)
    DAY_TIME = 'time (utc)'
    DAY_TEMP = 'tempc'
    DAY_WIND = 'speedkph'
    DAY_RAIN = 'rain mncm'
    DAY_RH = 'humidity%'
    DAY_PRESSURE = 'barometermb'


class CWOP(RMParser):
    parserName = "Weather Stations"
    parserDescription = "Observed data from World-Wide Weather Stations Citizen Weather Observer Program"
    parserForecast = False
    parserHistorical = True
    parserEnabled = True
    parserDebug = False
    parserInterval = 6 * 3600
    params = {
        '_stations': [],
        'selectedStation': None,
        "_recommendedDistance": 20,
    }

    def perform(self):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'}
        lat = self.settings.location.latitude
        lon = self.settings.location.longitude
        #lat = 37.677
        #lon = -121.886
        dataURL = 'http://www.findu.com/cgi-bin/wxnear.cgi?lat=%s&lon=%s' % (lat, lon)
        d = self.openURL(dataURL, headers=headers)
        if not d:
            log.error("Cannot open %s" % dataURL)
            return

        html = d.read()
        html = html.lower()
        startToken = '<table'
        endToken = '</table>'
        part = html[html.find(startToken): html.rfind(endToken) + len(endToken)]
        tree = ET.fromstring(part)
        row = 0
        headerHints = OrderedDict()
        weatherData = []
        firstDirectionIdx = None  # The report has direction twice

        # -------------------------------------------------------------------------------------------------------------
        # Get all nearby stations info
        #
        for elem in tree.iter('tr'):
            stationData = []
            for idx, elemData in enumerate(elem.iterfind('td')):
                if row == 0:
                    key = elemData.text.strip()
                    if key == 'direction' and firstDirectionIdx is None:
                        firstDirectionIdx = idx
                        headerHints[key + '_skip'] = idx
                    else:
                        headerHints[key] = idx
                else:
                    link = elemData.find('a')
                    if link is not None and link.text is not None:
                        stationData.append(link.text.strip())
                    else:
                        if idx == firstDirectionIdx or elemData.text is None:
                            stationData.append(None)
                        else:
                            stationData.append(elemData.text.strip())

            if row > 0:
                weatherData.append(stationData)

            row += 1

        if len(weatherData) == 0:
            log.error('No nearby stations')
            return

        # -------------------------------------------------------------------------------------------------------------
        # Parse nearby stations data
        # We can't use this "last" values for weather data in RainMachine because if this parser runs 4 times
        # per day (every 6 hours) we'll only have 4 values which won't represent how the day actually went
        # so we need to retrieve all day observation from the selected station (see below)

        self.params["_stations"] = []
        selectedStation = weatherData[0]

        for station in weatherData:
            #log.info("%s: " % station[headerHints[CWOPKeys.NAME]]),
            skipStation = False
            for key in headerHints:
                if key == CWOPKeys.NAME:
                    continue
                elif key == CWOPKeys.RAIN:
                    station[headerHints[key]] = convertInchesToMM(station[headerHints[key]])
                elif key == CWOPKeys.TEMP:
                    station[headerHints[key]] = convertFahrenheitToCelsius(station[headerHints[key]])
                elif key == CWOPKeys.WIND:
                    station[headerHints[key]] = convertMPHToMS(station[headerHints[key]])
                elif key == CWOPKeys.DISTANCE:
                    station[headerHints[key]] = convertMilesToKM(station[headerHints[key]])
                    if station[headerHints[key]] > 30:
                        skipStation = True
                elif key == CWOPKeys.PRESSURE:
                    station[headerHints[key]] = convertToFloat(station[headerHints[key]])
                    if station[headerHints[key]] is not None:
                        station[headerHints[key]] /= 10
                elif key == CWOPKeys.LAST_SEEN:
                    station[headerHints[key]] = self._ageToSeconds(station[headerHints[key]])
                    if station[headerHints[key]] > 12 * 3600:
                        skipStation = True

                log.debug('%s: %s' % (key, station[headerHints[key]]))

            if not skipStation:
                self.params['_stations'].append(
                    (station[headerHints[CWOPKeys.NAME]].upper(), round(station[headerHints[CWOPKeys.DISTANCE]]))
                )
                if self.params['selectedStation'] is not None and station[headerHints[CWOPKeys.NAME]].upper() == self.params['selectedStation'].upper():
                    selectedStation = station

        #log.info(self.params['_stations'])

        # -------------------------------------------------------------------------------------------------------------
        # Get day data for selected station
        #
        if selectedStation:
            dataURL = 'http://www.findu.com/cgi-bin/wx.cgi?call=%s&units=metric' % selectedStation[headerHints[CWOPKeys.NAME]]
            d = self.openURL(dataURL, headers=headers)
            if not d:
                log.error("Cannot open %s" % dataURL)
                return

            html = d.read()
            html = html.lower()
            html = html.replace('<br>', '')
            startToken = '<table'
            endToken = '</table>'
            part = html[html.find(startToken): html.rfind(endToken) + len(endToken)]
            tree = ET.fromstring(part)
            # -------------------------------------------------------------------------------------------------------------
            # Parse station data
            #
            row = 0
            headerHintsDay = OrderedDict()
            stationAllData = []
            maxOlderDay = rmCurrentDayTimestamp()
            #log.info("Today: %s / %s maxOlderDay: %s" % (rmCurrentTimestampToDateAsString(), rmTimestampToDateAsString(rmCurrentTimestamp()), rmTimestampToDateAsString(maxOlderDay)))
            for elem in tree.iter('tr'):
                rowData = []
                for idx, elemData in enumerate(elem.iterfind('td')):
                    if row == 0:
                        key = elemData.text.strip()
                        headerHintsDay[key] = idx
                    else:
                        try:
                            value = elemData.text.strip()
                            if idx == headerHintsDay[CWOPKeys.DAY_TIME]:
                                # log.info("Date: %s / %s (%s) maxOlder: %s" % (value,
                                #     rmTimestampToDateAsString(rmTimestampFromDateAsString(value, "%Y%m%d%H%M%S")),
                                #     rmTimestampFromDateAsString(value, "%Y%m%d%H%M%S"),
                                #     maxOlderDay))
                                value = rmTimestampFromDateAsString(value, "%Y%m%d%H%M%S") # UTC Time
                                if value < maxOlderDay:
                                    #log.info("Ignore entry with timestamp %s too old" % value)
                                    break
                            elif idx == headerHintsDay[CWOPKeys.DAY_RAIN]:
                                value = convertToFloat(value)
                                if value is not None:
                                    value *= 10 # cm to mm
                            elif idx == headerHintsDay[CWOPKeys.DAY_TEMP]:
                                value = convertToInt(value)
                            elif idx == headerHintsDay[CWOPKeys.DAY_WIND]:
                                value = convertToFloat(value)
                                if value is not None:
                                    value /= 3.6
                            elif idx == headerHintsDay[CWOPKeys.DAY_RH]:
                                value = convertToInt(value)
                            elif idx == headerHintsDay[CWOPKeys.DAY_PRESSURE]:
                                value = convertToFloat(value)
                                if value is not None:
                                    value /= 10 # mb to kpa

                            rowData.append(value)
                        except Exception, e:
                            log.error(e)

                if rowData:
                    timestamp = rowData[headerHintsDay[CWOPKeys.DAY_TIME]]
                    temp = rowData[headerHintsDay[CWOPKeys.DAY_TEMP]]
                    rh = rowData[headerHintsDay[CWOPKeys.DAY_RH]]
                    wind = rowData[headerHintsDay[CWOPKeys.DAY_WIND]]
                    rain = rowData[headerHintsDay[CWOPKeys.DAY_RAIN]]
                    pressure = rowData[headerHintsDay[CWOPKeys.DAY_PRESSURE]]

                    # instant values
                    self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temp, False)
                    self.addValue(RMParser.dataType.RH, timestamp, rh, False)
                    self.addValue(RMParser.dataType.WIND, timestamp, wind, False)
                    self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure, False)

                    # Since midnight value
                    self.addValue(RMParser.dataType.RAIN, rmGetStartOfDay(timestamp), rain, False)
                    stationAllData.append(rowData)

                row += 1

            # -------------------------------------------------------------------------------------------------------------
            # Debug aggregates
            #
            # dayAggregates = {}
            # prevDay = None
            # currentDay = None
            # for entry in stationAllData:
            #     currentDay = rmGetStartOfDay(entry[headerHintsDay[CWOPKeys.DAY_TIME]])
            #     if currentDay != prevDay:
            #         log.info("New day %s" % rmTimestampToDateAsString(currentDay))
            #         dayAggregates[currentDay] = {
            #             "maxt": -9999,
            #             "mint": 9999,
            #             "rain": -9999,
            #             "rh": 0,
            #             "rh_count": 0,
            #             "pressure": 0,
            #             "pressure_count": 0,
            #             "wind": 0,
            #             "wind_count": 0
            #         }
            #         if prevDay is not None and prevDay in dayAggregates:
            #             dayAggregates[prevDay]["rh"] = dayAggregates[prevDay]["rh"] / dayAggregates[prevDay]["rh_count"]
            #             dayAggregates[prevDay]["pressure"] = dayAggregates[prevDay]["pressure"] / dayAggregates[prevDay]["pressure_count"]
            #             dayAggregates[prevDay]["wind"] = dayAggregates[prevDay]["wind"] / dayAggregates[prevDay]["wind_count"]
            #
            #         prevDay = currentDay
            #
            #     if entry[headerHintsDay[CWOPKeys.DAY_TEMP]] > dayAggregates[currentDay]["maxt"]:
            #         dayAggregates[currentDay]["maxt"] = entry[headerHintsDay[CWOPKeys.DAY_TEMP]]
            #
            #     if entry[headerHintsDay[CWOPKeys.DAY_TEMP]] < dayAggregates[currentDay]["mint"]:
            #         dayAggregates[currentDay]["mint"] = entry[headerHintsDay[CWOPKeys.DAY_TEMP]]
            #
            #     if entry[headerHintsDay[CWOPKeys.DAY_RAIN]] > dayAggregates[currentDay]["rain"]:
            #         dayAggregates[currentDay]["rain"] = entry[headerHintsDay[CWOPKeys.DAY_RAIN]]
            #
            #     dayAggregates[currentDay]["rh"] += entry[headerHintsDay[CWOPKeys.DAY_RH]]
            #     dayAggregates[currentDay]["rh_count"] += 1
            #
            #     dayAggregates[currentDay]["pressure"] += entry[headerHintsDay[CWOPKeys.DAY_PRESSURE]]
            #     dayAggregates[currentDay]["pressure_count"] += 1
            #
            #     dayAggregates[currentDay]["wind"] += entry[headerHintsDay[CWOPKeys.DAY_WIND]]
            #     dayAggregates[currentDay]["wind_count"] += 1
            #
            # # current day left overs
            #
            # dayAggregates[currentDay]["rh"] = dayAggregates[currentDay]["rh"] / dayAggregates[currentDay]["rh_count"]
            # dayAggregates[currentDay]["pressure"] = dayAggregates[currentDay]["pressure"] / dayAggregates[currentDay]["pressure_count"]
            # dayAggregates[currentDay]["wind"] = dayAggregates[currentDay]["wind"] / dayAggregates[currentDay]["wind_count"]
            #
            # for day in dayAggregates:
            #     log.info(dayAggregates[day])

    def _ageToSeconds(self, ageStr):
        try:
            d,h,m,s = ageStr.split(':')
            return int(d) * 86400 + int(h) * 3600 + int(m) * 60 + int(s)
        except:
            pass
        return None

if __name__ == "__main__":
    p = CWOP()
    p.perform()