# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>
#   Meteobridge parser:
#          Gordon Larsen    <gordon@the-larsens.ca>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
#from RMUtilsFramework.rmTimeUtils import rmNowDateTime, rmGetStartOfDay
#from RMDataFramework.rmUserSettings import globalSettings
#import time
import datetime, calendar
#from urllib import urlopen
#from requests.auth import HTTPBasicAuth
import requests

# class PWSMeteobridge(RMParser):
class Meteobridge_parser():
    parserName = "Meteobridge PWS Parser"
    parserDescription = "Personal Weather Station direct data upload from Meteobridge"
    parserForecast = False
    parserHistorical = True
    parserEnabled = True
    parserDebug = True
    parserInterval = 1 * 60
    params = {"top_level_url": "meteobridge.internal.home",
              "username": "meteobridge",
              "password": "meteobridge"
              }


    def perform(self):


        user = self.params.get("username")
        passwd = self.params.get("password")

        top_level_url = self.params.get("top_level_url")
        urlPath = "http://" + user + ":" + passwd + "@" + top_level_url + "/cgi-bin/template.cgi?template="

        values = "[th0temp-act]%20[th0hum-act]%20[thb0press-act]%20[sol0evo-act]%20[mbsystem-latitude]%20" \
                 "[mbsystem-longitude]%20[th0temp-dmax]%20[th0temp-dmin]%20[th0hum-dmax]%20" \
                  "[th0hum-dmin]%20[wind0avgwind-act]%20[sol0rad-act]%20[rain0total-daysum]%20" \
                 "[th0dew-act]%20[UYYYY][UMM][UDD][Uhh][Umm][Uss]&contenttype=text/plain;charset=iso-8859-1"
        headers = {''}

        log.debug(str(urlPath) + str(values))

        try:
            d = requests.get(urlPath + values)
            dstr = str(d)

            if dstr.find("200") is -1:
                log.error("Invalid username or password")
                return

        except AssertionError as error:
            log.error(str(error))
            log.error("Cannot open Meteobridge")

        pwsContent = d.content
        log.debug(pwsContent)
        #pwsContent = pwsContent.strip('b')
        #pwsContent = pwsContent.strip("'")
        pwsArray = pwsContent.split(" ")
        log.debug(pwsArray)

        lat = float(pwsArray[4])
        long = float(pwsArray[5])

        temperature = float(pwsArray[0])
        et0 = float(pwsArray[3])
        mintemp = float(pwsArray[7])
        maxtemp = float(pwsArray[6])
        rh = float(pwsArray[1])
        minrh = float(pwsArray[9])
        maxrh = float(pwsArray[8])
        wind = float(pwsArray[10])
        solarradiation = float(pwsArray[11])  # needs to be converted from watt/sqm*h to Joule/sqm
        #log.debug(str(temperature) + " " + str(et0) + " " + str(mintemp) + " " + str(maxtemp) +
        #         " " + str(rh) + " " + str(wind) + " " + str(solarradiation))

        if solarradiation is not None:
            solarradiation *= 0.0864

        rain = float(pwsArray[12])
        dewpoint = float(pwsArray[13])
        pressure = float(pwsArray[2]) / 10

        # time utc
        jutc = pwsArray[14]
        log.debug(str(jutc))

        yyyy = self.__toInt(jutc[:4])
        mm = self.__toInt(jutc[4:6])
        dd = self.__toInt(jutc[6:8])
        hour = self.__toInt(jutc[8:10])
        mins = self.__toInt(jutc[10:12])
        log.debug("Observations for date: %d/%d/%d, time: %d%dz Temp: %s, Rain: %s" % (yyyy, mm, dd, hour, mins, temperature, rain))

        dd = datetime.datetime(yyyy, mm, dd, hour, mins)
        timestamp = calendar.timegm(dd.timetuple())
        timestamp = self.__parseDateTime(timestamp)

        self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temperature)
        self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp)
        self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp)
        self.addValue(RMParser.dataType.RH, timestamp, rh)
        self.addValue(RMParser.dataType.MINRH, timestamp, minrh)
        self.addValue(RMParser.dataType.MAXRH, timestamp, maxrh)
        self.addValue(RMParser.dataType.WIND, timestamp, wind)
        self.addValue(RMParser.dataType.RAIN, timestamp, rain)
        self.addValue(RMParser.dataType.ET0, timestamp, et0)
        # self.addValue(RMParser.dataType.QPF, timestamp, rain) # uncomment to report measured rain as previous day QPF
        self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint)
        self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)

        return


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
        # type: (object) -> object
        try:
            if value is None:
                return value
            return int(value)
        except:
            return None

if __name__ == "__main__":
    p = Meteobridge_parser()
    p.perform()
# aa=perform('self')
