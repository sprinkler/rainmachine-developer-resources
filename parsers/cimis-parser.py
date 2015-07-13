# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>
#          Virgil Dinu <virgil.dinu@coretech.ro>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *

import datetime
import json

class CIMIS(RMParser):
    parserName = "CIMIS Parser"
    parserID = "cimis"
    parserInterval = 6 * 3600
    parserEnabled = False
    parserDebug = True
    params = {"customStation": True, "station": 2, "historicDays": 5, "appKey": None}
    #params = {"customStation": True, "station": 2, "historicDays": 5, "appKey": "523cf689-7ba6-47bd-a2be-6dc1c1ba9afb"}

    maxAllowedDays = 80 # the maximum number of days CIMIS allows to retrieve in 1 call

    def isEnabledForLocation(self, timezone, lat, long):
        if CIMIS.parserEnabled:
            appKey = self.params.get("appKey", None)
            return appKey is not None
        return False

    def perform(self):

        days = self.params["historicDays"]
        intervals = days / self.maxAllowedDays + (days % self.maxAllowedDays != 0)
        lastIntervalStartDay = datetime.date.today()

        if intervals > 1:
            days = self.maxAllowedDays

        log.debug("Days: %d Intervals: %d" % (days, intervals))

        for i in range(0, intervals):
            startDay = lastIntervalStartDay - datetime.timedelta(days=1) #CIMIS real data starts from yesterday
            endDay = startDay - datetime.timedelta(days=(days + 1))
            lastIntervalStartDay = endDay
            try:
                log.debug("Running CIMIS for startDay: %s endDay: %s" % (startDay, endDay))
                self.__retrieveData(endDay, startDay) # we call with startDay/endDay swapped because CIMIS expects historic intervals
            except Exception, e:
                log.error("*** Error running cimis parser")
                log.exception(e)

        log.debug("Finished running cimis parser")


    def __retrieveData(self, startDate, endDate):
        useCustomStation = self.params["customStation"]
        customStation = self.params["station"]
        appKey = self.params["appKey"]

        s = self.settings
        URL = "http://et.water.ca.gov/api/data"
        
        # bad req if lat;lon is not in CA.
        dataItems = "day-asce-eto,day-precip,day-sol-rad-avg,day-vap-pres-avg,day-air-tmp-max," + \
                    "day-air-tmp-min,day-air-tmp-avg,day-rel-hum-max,day-rel-hum-min,day-rel-hum-avg," + \
                    "day-dew-pnt,day-wind-spd-avg,day-wind-run,day-soil-tmp-avg"

        if useCustomStation:
            URLParams = "appKey={0}&targets={1}&startDate={2}&endDate={3}&unitOfMeasure={4}".format\
                    (
                    appKey,
                    customStation,
                    startDate,
                    endDate,
                    "M"
                    )
        else:
            URLParams = "appKey={0}&targets=lat={1},lng={2}&dataItems={3}&startDate={4}&endDate={5}&unitOfMeasure={6}".format\
                    (
                    appKey,
                    s.location.latitude,
                    s.location.longitude,
                    dataItems,
                    startDate,
                    endDate,
                    "M"
                    )

        #Non-standard URL parameters
        #URLParams = \
        #    [
        #        ("appKey", self.appKey),
        #        ("targets", "lat=" + `s.location.latitude` + ",lng=" + `s.location.longitude`), # multiple locations separated by ";"
        #        ("dataItems", "day-asce-eto,day-precip,day-sol-rad-avg,day-vap-pres-avg,day-air-tmp-max,day-air-tmp-min,day-air-tmp-avg,day-rel-hum-max,day-rel-hum-min,day-rel-hum-avg,day-dew-pnt,day-wind-spd-avg,day-wind-run,day-soil-tmp-avg"),
        #        ("startDate", startDate),
        #        ("endDate", endDate),
        #        ("unitOfMeasure", "M")
        #    ]

        try:
            d = self.openURL(URL, URLParams, encodeParameters=False)
            if d is None:
                return

            observation = json.loads(d.read())

            daily = []

            try:
                daily = observation["Data"]["Providers"][0]["Records"]
            except Exception, e:
                log.error("*** No daily information found in response!")
                log.exception(e)

            for entry in daily:
                timestamp = entry.get("Date")
                if timestamp is None:
                    continue
                
                timestamp = int(time.mktime(datetime.datetime.strptime(timestamp, "%Y-%m-%d").timetuple()))
                avgTemp = entry.get("DayAirTmpAvg")["Value"]
                minTemp = entry.get("DayAirTmpMin")["Value"]
                maxTemp = entry.get("DayAirTmpMax")["Value"]

                if avgTemp is None or minTemp is None or maxTemp is None:
                    continue

                self.addValue(RMParser.dataType.TEMPERATURE, timestamp, self.__toFloat(avgTemp))
                self.addValue(RMParser.dataType.MINTEMP, timestamp, self.__toFloat(minTemp))
                self.addValue(RMParser.dataType.MAXTEMP, timestamp, self.__toFloat(maxTemp))
                self.addValue(RMParser.dataType.QPF, timestamp, self.__toFloat(entry.get("DayPrecip")["Value"]))
                self.addValue(RMParser.dataType.RH, timestamp, self.__toFloat(entry.get("DayRelHumAvg")["Value"]))
                self.addValue(RMParser.dataType.MINRH, timestamp, self.__toFloat(entry.get("DayRelHumMin")["Value"]))
                self.addValue(RMParser.dataType.MAXRH, timestamp, self.__toFloat(entry.get("DayRelHumMax")["Value"]))
                self.addValue(RMParser.dataType.WIND, timestamp, self.__toFloat(entry.get("DayWindSpdAvg")["Value"]))
                self.addValue(RMParser.dataType.RAIN, timestamp, self.__toFloat(entry.get("DayPrecip")["Value"]))
                self.addValue(RMParser.dataType.DEWPOINT, timestamp, self.__toFloat(entry.get("DayDewPnt")["Value"]))
                self.addValue(RMParser.dataType.PRESSURE, timestamp, self.__toFloat(entry.get("DayVapPresAvg")["Value"]))
                self.addValue(RMParser.dataType.ET0, timestamp, self.__toFloat(entry.get("DayAsceEto")["Value"]))

                # We receive solar radiation in watt/m2 we need in mjoules/m2
                solarRadiation = self.__toFloat(entry.get("DaySolRadAvg")["Value"])
                if solarRadiation is not None:
                    solarRadiation *= 0.0864;

                self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, solarRadiation)

            if self.parserDebug:
                log.debug(self.result)

        except Exception, e:
            log.error("*** Error retrieving data from cimis")
            log.exception(e)

    def __toFloat(self, value):
        if value is None:
            return value
        return float(value)