# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import sys
sys.path.append('../')

from RMDataFramework.rmForecastInfo import RMForecastInfo
from RMDataFramework.rmWeatherData import *
from RMDataFramework.rmMixerData import *

from rmDatabase import *
from rmForecastInfoTable import *
from rmLimitsTable import *
from rmParserDataTable import *
from rmMixerDataTable import *

db = RMParsersDatabase("/home/codrin/rainmachine.sqlite")
db.open()

parserTable = RMParserTable(db)

try:
    parserTable.addParser("noaa")
    parserTable.addParser("forecast.io")
except Exception as e:
    print e

forecastTable = RMForecastTable(db)
limitsTable = RMLimitsTable(db)
parserDataTable = RMParserDataTable(db)
mixerDataTable = RMMixerDataTable(db)


forecast = forecastTable.addRecord()

#limitsTable.addRecord("parser", "qaz", 1)
#limitsTable.addRecords([("parser", "p1", 1, 10), ("parser", "p2", 1, 12.3), ("parser", "p3", None, 12.3)])

print limitsTable.getRecord("parser", "p3")

parserValues = [
    RMWeatherData(2001, None, -18, 83, 14.5),
    RMWeatherData(2002, 13, None, 90),
    RMWeatherData(3003, 4, -6, None),
    RMWeatherData(3004, 5, -5, 141, 93.2),
    RMWeatherData(3009, -23, -5, 111),
]
parserDataTable.addRecords(forecast.id, 2, parserValues)

mixerValues = [
    RMMixerData(2001, None, -18, 83, 14.5),
    RMMixerData(2002, 13, None, 90, et0calc=12.9),
    RMMixerData(3003, 4, -6, None),
    RMMixerData(3004, 5, -5, 141, 93.2, et0final=98.1),
    RMMixerData(3009, -23, -5, 111),
]
mixerDataTable.addRecords(forecast.id, mixerValues)


#parserDataTable.deleteRecordsByTimestampThreshold(1, 2003, 3003)

print (14.5 + 90 + 93.2) / 3
