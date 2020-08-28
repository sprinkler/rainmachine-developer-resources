# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
from RMUtilsFramework.rmLogging import log
from RMOSGlue.rmOSPlatform import RMOSPlatform
from RMUtilsFramework.rmUtils import convertKnotsToMS
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp

class PWS(RMParser):
    parserName = "WeatherDisplay Parser"
    parserDescription = "Personal Weather Station direct data download in WeatherDisplay raw format"
    parserForecast = False
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600
    params = {"urlPath" : "http://weather-display.com/windy/clientraw.txt", "maxAllowedDistance": 100000}

    def isEnabledForLocation(self, timezone, lat, long):
        return PWS.parserEnabled

    def distanceToStation(self, lat, lon):
        if RMOSPlatform().AUTODETECTED == RMOSPlatform.SIMULATED:
            llat = 47.1550897
            llon = 27.5815751
        else:
            s = self.settings
            llat = s.location.latitude
            llon = s.location.longitude
        return distanceBetweenGeographicCoordinatesAsKm(lat, lon, llat, llon)

    def perform(self):
        URL = self.params.get("urlPath", None)
        d = self.openURL(URL)
        if d is None:
             return
        pwsContent = d.read()
        if pwsContent is None:
             return

        pwsContent = pwsContent.strip()
        pwsArray = pwsContent.split(" ")

        lat = float(pwsArray[160])
        lon = -float(pwsArray[161])

        distToPWS = self.distanceToStation(lat, lon)
        maxDist = self.params.get("maxAllowedDistance")
        if(distToPWS > maxDist):
             log.error("*** PWS Station too far from home!")
             return


        temperature = self.__toFloat(pwsArray[4])
        mintemp = self.__toFloat(pwsArray[47])
        maxtemp = self.__toFloat(pwsArray[46])
        rh = self.__toFloat(pwsArray[5])
        minrh = self.__toFloat(pwsArray[164])
        maxrh = self.__toFloat(pwsArray[163])
        wind = self.__toFloat(convertKnotsToMS(pwsArray[1]))  # converted from knos to m/s
        solarradiation = self.__toFloat(pwsArray[127])  # needs to be converted from watt/sqm*h to Joule/sqm

        if solarradiation is not None:
                    solarradiation *= 0.0864

        rain = self.__toFloat(pwsArray[7])
        dewpoint = self.__toFloat(pwsArray[72])
        pressure = self.__toFloat(pwsArray[50])
        conditionIcon = self.conditionConvert(self.__toFloat(pwsArray[48]))
        #skycover ?

        timestamp = rmCurrentTimestamp()
        self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temperature)
        self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp)
        self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp)
        self.addValue(RMParser.dataType.RH, timestamp, rh)
        self.addValue(RMParser.dataType.MINRH, timestamp, minrh)
        self.addValue(RMParser.dataType.MAXRH, timestamp, maxrh)
        self.addValue(RMParser.dataType.WIND, timestamp, wind)
        self.addValue(RMParser.dataType.RAIN, timestamp, rain)
        self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint)
        self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)
        self.addValue(RMParser.dataType.CONDITION, timestamp, conditionIcon)
        self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, solarradiation)

        print self.result
        return

    def conditionConvert(self, iconIndex):
        if iconIndex==0:
            return RMParser.conditionType.Fair
        elif iconIndex==1:
            return RMParser.conditionType.Fair
        elif iconIndex==2:
            return RMParser.conditionType.MostlyCloudy
        elif iconIndex==3:
            return RMParser.conditionType.PartlyCloudy
        elif iconIndex==4:
            return RMParser.conditionType.MostlyCloudy
        elif iconIndex==5:
            return  RMParser.conditionType.Unknown #dry
        elif iconIndex==6:
            return  RMParser.conditionType.Fog
        elif iconIndex==7:
            return  RMParser.conditionType.Haze
        elif iconIndex==8:
            return  RMParser.conditionType.HeavyRain
        elif iconIndex==9:
            return  RMParser.conditionType.FewClouds
        elif iconIndex==10:
            return  RMParser.conditionType.Haze
        elif iconIndex==11:
            return  RMParser.conditionType.Fog
        elif iconIndex==12:
            return  RMParser.conditionType.HeavyRain
        elif iconIndex==13:
            return  RMParser.conditionType.Overcast
        elif iconIndex==14:
            return  RMParser.conditionType.HeavyRain
        elif iconIndex==15:
            return  RMParser.conditionType.RainShowers
        elif iconIndex==16:
            return  RMParser.conditionType.Snow
        elif iconIndex==17:
            return  RMParser.conditionType.Thunderstorm
        elif iconIndex==18:
            return  RMParser.conditionType.Overcast
        elif iconIndex==19:
            return  RMParser.conditionType.PartlyCloudy
        elif iconIndex==20:
            return  RMParser.conditionType.HeavyRain
        elif iconIndex==21:
            return  RMParser.conditionType.HeavyRain
        elif iconIndex==22:
            return  RMParser.conditionType.RainShowers
        elif iconIndex==23:
            return  RMParser.conditionType.IcePellets
        elif iconIndex==24:
            return  RMParser.conditionType.IcePellets
        elif iconIndex==25:
            return  RMParser.conditionType.Snow
        elif iconIndex==26:
            return  RMParser.conditionType.Snow
        elif iconIndex==27:
            return  RMParser.conditionType.Snow
        elif iconIndex==28:
            return  RMParser.conditionType.Fair
        elif iconIndex==29:
            return  RMParser.conditionType.Thunderstorm
        elif iconIndex==30:
            return  RMParser.conditionType.Thunderstorm
        elif iconIndex==31:
            return  RMParser.conditionType.Thunderstorm
        elif iconIndex==32:
            return  RMParser.conditionType.FunnelCloud #tornado
        elif iconIndex==33:
            return  RMParser.conditionType.Windy
        elif iconIndex==34:
            return  RMParser.conditionType.LightRain
        elif iconIndex==35:
            return  RMParser.conditionType.LightRain
        else:
            return  RMParser.conditionType.Unknown


    def __toFloat(self, value):
            if value is None:
                return value
            return float(value)
    # TIMESTAMP = "TIMESTAMP"
    # TEMPERATURE = "TEMPERATURE"             #[degC]
    # MINTEMP = "MINTEMP"                     #[degC]
    # MAXTEMP = "MAXTEMP"                     #[degC]
    # RH = "RH"                               #[percent]
    # MINRH = "MINRH"                         #[percent]
    # MAXRH = "MAXRH"                         #[percent]
    # WIND = "WIND"                           #[meter/sec]
    # SOLARRADIATION = "SOLARRADIATION"       #[megaJoules / square meter per hour]
    # SKYCOVER = "SKYCOVER"                   #[percent]
    # RAIN = "RAIN"                           #[mm]
    # ET0 = "ET0"                             #[mm]
    # POP = "POP"                             #[percent]
    # QPF = "QPF"                             #[mm] -
    # CONDITION = "CONDITION"                 #[string]
    # PRESSURE = "PRESSURE"                   #[kilo Pa]
    # DEWPOINT = "DEWPOINT"                   #[degC]
    # USERDATA = "USERDATA"

#
# aa = PWS()
#
# aa.perform()