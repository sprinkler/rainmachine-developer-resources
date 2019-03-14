# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from datetime import datetime
from RMUtilsFramework.rmLogging import log
from rmParserUserData import RMParserUserData

# List from http://w1.weather.gov/xml/current_obs/weather.php
# and http://www.nws.noaa.gov/xml/xml_fields_icon_weather_conditions.php
class RMWeatherConditions:
    (
        MostlyCloudy,
        Fair,
        FewClouds,
        PartlyCloudy,
        Overcast,
        Fog,
        Smoke,
        FreezingRain,
        IcePellets,
        RainIce,
        RainSnow,
        RainShowers,
        Thunderstorm,
        Snow,
        Windy,
        ShowersInVicinity,
        HeavyFreezingRain,
        ThunderstormInVicinity,
        LightRain,
        HeavyRain,
        FunnelCloud,
        Dust,
        Haze,
        Hot,
        Cold,
        Unknown
    ) = range(0, 26)

class RMWeatherDataType:
    TIMESTAMP = "TIMESTAMP"
    TEMPERATURE = "TEMPERATURE"             #[degC]
    MINTEMP = "MINTEMP"                     #[degC]
    MAXTEMP = "MAXTEMP"                     #[degC]
    RH = "RH"                               #[percent]
    MINRH = "MINRH"                         #[percent]
    MAXRH = "MAXRH"                         #[percent]
    WIND = "WIND"                           #[meter/sec]
    SOLARRADIATION = "SOLARRADIATION"       #[megaJoules / square meter per hour]
    SKYCOVER = "SKYCOVER"                   #[percent]
    RAIN = "RAIN"                           #[mm]
    ET0 = "ET0"                             #[mm]
    POP = "POP"                             #[percent]
    QPF = "QPF"                             #[mm] -
    CONDITION = "CONDITION"                 #[string]
    PRESSURE = "PRESSURE"                   #[kilo Pa]
    DEWPOINT = "DEWPOINT"                   #[degC]
    USERDATA = "USERDATA"

class RMWeatherData:
    def __init__(self, timestamp = None, useCounters = False):
        self.timestamp = timestamp
        self.temperature = None
        self.minTemperature = None
        self.maxTemperature = None
        self.rh = None
        self.minRh = None
        self.maxRh = None
        self.wind = None
        self.solarRad = None
        self.skyCover = None
        self.rain = None
        self.et0 = None
        self.pop = None
        self.qpf = None
        self.condition = None
        self.pressure = None
        self.dewPoint = None
        self.userData = None

        self.useCounters = useCounters
        if useCounters:
            self.activateCounters()

    def __repr__(self):
        return "(" + self.toString() + ")"

    def activateCounters(self):
        self.useCounters = True
        self.temperatureCounter = 0
        self.minTemperatureCounter = 0
        self.maxTemperatureCounter = 0
        self.rhCounter = 0
        self.minRhCounter = 0
        self.maxRhCounter = 0
        self.windCounter = 0
        self.solarRadCounter = 0
        self.skyCoverCounter = 0
        self.rainCounter = 0
        self.et0Counter = 0
        self.popCounter = 0
        self.qpfCounter = 0
        self.conditionCounter = 0
        self.pressureCounter = 0
        self.dewPointCounter = 0

    def toString(self):

        if self.useCounters:
            return `datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')` + \
                    ", temp=" + `self.temperature` + "/" + `self.temperatureCounter` + \
                    ", minTemp=" + `self.minTemperature` + "/" + `self.minTemperatureCounter` + \
                    ", maxTemp=" + `self.maxTemperature` + "/" + `self.maxTemperatureCounter` + \
                    ", rh=" + `self.rh` + "/" + `self.rhCounter` + \
                    ", minRh=" + `self.minRh` + "/" + `self.minRhCounter` + \
                    ", maxRh=" + `self.maxRh` + "/" + `self.maxRhCounter` + \
                    ", wind=" + `self.wind` + "/" + `self.windCounter` + \
                    ", solarRad=" + `self.solarRad` + "/" + `self.solarRadCounter` + \
                    ", skyCover=" + `self.skyCover` + "/" + `self.skyCoverCounter` + \
                    ", rain=" + `self.rain` + "/" + `self.rainCounter` + \
                    ", et0=" + `self.et0` + "/" + `self.et0Counter` + \
                    ", pop=" + `self.pop` + "/" + `self.popCounter` + \
                    ", qpf=" + `self.qpf` + "/" + `self.qpfCounter` + \
                    ", condition=" + `self.condition` + "/" + `self.conditionCounter` + \
                    ", pressure=" + `self.pressure` + "/" + `self.pressureCounter` + \
                    ", dewPoint=" + `self.dewPoint` + "/" + `self.dewPointCounter` + \
                    ", userData=" + `self.userData`

        return `datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')` + \
                ", temp=" + `self.temperature` + \
                ", minTemp=" + `self.minTemperature` + \
                ", maxTemp=" + `self.maxTemperature` + \
                ", rh=" + `self.rh` + \
                ", minRh=" + `self.minRh` +  \
                ", maxRh=" + `self.maxRh` +  \
                ", wind=" + `self.wind` + \
                ", solarRad=" + `self.solarRad` + \
                ", skyCover=" + `self.skyCover` + \
                ", rain=" + `self.rain` + \
                ", et0=" + `self.et0` + \
                ", pop=" + `self.pop` + \
                ", qpf=" + `self.qpf` + \
                ", condition=" + `self.condition` + \
                ", pressure=" + `self.pressure` + \
                ", dewPoint=" + `self.dewPoint` + \
                ", userData=" + `self.userData`

    def setValue(self, key, value):
        if key == RMWeatherDataType.TIMESTAMP:
            self.timestamp = int(value)
        elif key == RMWeatherDataType.CONDITION:
            self.condition = value
        elif key == RMWeatherDataType.USERDATA:
            self.userData = value
        else: # FORCE INTEGER/FLOAT
            try:
                if type(value) is str or type(value) is unicode:
                    value = float(value)
                if type(value) != 'int':
                    value = round(value, 2)
            except Exception, e:
                log.debug("Can't convert value '%s' to proper category type(%s) because %s" % (value, key, e))
                value = None

            if key == RMWeatherDataType.TEMPERATURE:
                self.temperature = value
            elif key == RMWeatherDataType.MINTEMP:
                self.minTemperature = value
            elif key == RMWeatherDataType.MAXTEMP:
                self.maxTemperature = value
            elif key == RMWeatherDataType.RH:
                self.rh = value
            elif key == RMWeatherDataType.MINRH:
                self.minRh = value
            elif key == RMWeatherDataType.MAXRH:
                self.maxRh = value
            elif key == RMWeatherDataType.WIND:
                self.wind = value
            elif key == RMWeatherDataType.SOLARRADIATION:
                self.solarRad = value
            elif key == RMWeatherDataType.SKYCOVER:
                self.skyCover = value
            elif key == RMWeatherDataType.RAIN:
                self.rain = value
            elif key == RMWeatherDataType.ET0:
                self.et0 = value
            elif key == RMWeatherDataType.POP:
                self.pop = value
            elif key == RMWeatherDataType.QPF:
                self.qpf = value
            elif key == RMWeatherDataType.PRESSURE:
                self.pressure = value
            elif key == RMWeatherDataType.DEWPOINT:
                self.dewPoint = value


    def setUserValue(self, key, value):
        if self.userData == None:
            self.userData = RMParserUserData()
        self.userData.setValue(key, value)
