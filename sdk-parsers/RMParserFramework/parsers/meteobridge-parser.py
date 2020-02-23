# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>
#   Meteobridge parser:
#          Gordon Larsen    <gordon@the-larsens.ca>
# Updates:
# 24-Aug-19 change wind template variable to wind0avgwind-davg wind0avgwind-act to capture daily average instead of
#           so that RM captures daily data correctly.

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from urllib import urlopen as request


class MeteobridgePWS(RMParser):
    parserName = "Meteobridge PWS Parser"
    parserDescription = "Personal Weather Station data upload from Meteobridge"
    parserForecast = False
    parserHistorical = True
    parserEnabled = True
    parserDebug = False
    parserInterval = 6 * 60 * 60

    params = {'IP_address': '',
              'password': ''
              }

    def isEnabledForLocation(self, timezone, lat, long):
        return MeteobridgePWS.parserEnabled

    def perform(self):

        passwd = self.params.get('password')
        # Username is static, can't be changed.
        user = "meteobridge"
        top_level_url = str(self.params.get("IP_address"))

        if str(top_level_url) == "":
            log.error("IP address or hostname invalid or missing")
            return

        urlpath = "http://" + user + ":" + passwd + "@" + top_level_url + "/cgi-bin/template.cgi?template="

        values = "[th0temp-act]%20[th0hum-act]%20[thb0press-act]%20[sol0evo-daysum]%20[mbsystem-latitude]%20" \
                 "[mbsystem-longitude]%20[th0temp-dmax]%20[th0temp-dmin]%20[th0hum-dmax]%20" \
                 "[th0hum-dmin]%20[wind0avgwind-davg]%20[sol0rad-act]%20[rain0total-daysum]%20" \
                 "[th0dew-act]%20[UYYYY][UMM][UDD][Uhh][Umm][Uss]%20[epoch]%20" \
                 "[mbsystem-station]%20[mbsystem-stationnum]"

        headers = "&contenttype=text/plain;charset=iso-8859-1"

        try:
            mburl = urlpath + values + headers
            d = request(str(mburl))

            mbrdata = d.read()
            log.debug("Returned data: {}".format(mbrdata))

        except AssertionError as error:
            log.error(str(error))
            log.error("Cannot open Meteobridge")
            return

        self.getstationdata(mbrdata)
        log.info("Updated data from Meteobridge")

        return

    def getstationdata(self, pwscontent):
        pwsArray = pwscontent.split(" ")

        lat = float(pwsArray[4])
        long = float(pwsArray[5])

        temperature = float(pwsArray[0])

        try:
            et0 = float(pwsArray[3])
            vp2plus = True

        except:
            et0 = 0
            vp2plus = False

        mintemp = float(pwsArray[7])
        maxtemp = float(pwsArray[6])
        rh = float(pwsArray[1])
        minrh = float(pwsArray[9])
        maxrh = float(pwsArray[8])
        wind = float(pwsArray[10])
        # wind = wind / 3.6 # the Meteobridge already reports in mps so conversion is not required

        if vp2plus:
            solarradiation = float(pwsArray[11])  # needs to be converted from watt/sqm*h to Joule/sqm

            if solarradiation is not None:
                solarradiation *= 0.0864

        else:
            solarradiation = 0

        # log.debug(str(temperature) + " " + str(et0) + " " + str(mintemp) + " " + str(maxtemp) +
        #          " " + str(rh) + " " + str(wind) + " " + str(solarradiation))

        rain = float(pwsArray[12])
        dewpoint = float(pwsArray[13])
        pressure = float(pwsArray[2]) / 10

        if self.parserDebug:
            self.__toUtc(pwsArray[14], temperature, rain, wind)

        timestamp = int(pwsArray[15])
        stationtype = pwsArray[16]
        stationnum = pwsArray[17]
        log.debug("Weather station type: {0} ({1})".format(stationtype, stationnum))

        self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temperature)
        self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp)
        self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp)
        self.addValue(RMParser.dataType.RH, timestamp, rh)
        self.addValue(RMParser.dataType.MINRH, timestamp, minrh)
        self.addValue(RMParser.dataType.MAXRH, timestamp, maxrh)
        self.addValue(RMParser.dataType.WIND, timestamp, wind)
        self.addValue(RMParser.dataType.RAIN, timestamp, rain)
        if vp2plus:
            log.debug("addValue update - VP2: {}".format(vp2plus))
            self.addValue(RMParser.dataType.ET0, timestamp, et0)
            self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, solarradiation)

        # self.addValue(RMParser.dataType.QPF, timestamp, rain) # uncomment to report measured rain as previous day QPF
        self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint)
        self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)

    def __toFloat(self, value):
        if value is None:
            return value
        return float(value)

    def __parseDateTime(self, timestamp, roundToHour=True):
        if timestamp is None:
            return None
        if roundToHour:
            return timestamp - (timestamp % 3600)
        else:
            return timestamp

    def __toInt(self, value):
        try:
            if value is None:
                return value
            return int(value)
        except:
            return None

    def __toUtc(self, jutc, t, r, w):

        # time utc
        yyyy = self.__toInt(jutc[:4])
        mm = self.__toInt(jutc[4:6])
        dd = self.__toInt(jutc[6:8])
        hour = self.__toInt(jutc[8:10])
        mins = self.__toInt(jutc[10:12])
        log.debug("Observations for date: {:d}/{:d}/{:d}, time: {:d}{:d}z Temp: {}, Rain: {}, Wind: {}"
                  .format(yyyy, mm, dd, hour, mins, t, r, w))


#if __name__ == "__main__":
#    p = MeteobridgePWS()
#    p.perform()
