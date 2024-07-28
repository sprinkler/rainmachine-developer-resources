from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging
from RMUtilsFramework.rmTimeUtils import * #rmNowDateTime, rmGetStartOfDay, rmCurrentDayTimestamp, rmDeltaDayFromTimestamp, rmCurrentTimestamp

import json
from datetime import datetime
from HTMLParser import HTMLParser
import re


class NoaaTableParser(HTMLParser):

    #Initializing lists
    tableList = []
    tableRef = None
    rowRef = None
    colRef = None

    #HTML Parser Methods
    def handle_starttag(self, startTag, attrs):
        if startTag == 'table':
            self.tableList.append([])
            self.tableRef = self.tableList[-1]
        elif startTag == 'tr':
            self.tableRef.append([])
            self.rowRef = self.tableRef[-1]
        elif startTag == 'th':
            #This may span cols, so add additional columns to bridge the span
            numCols = 1
            for tup in attrs:
                if tup[0] == 'colspan':
                    numCols = int(tup[1])
                    break
            self.rowRef += ['']*numCols
            self.colRef = self.rowRef
        elif startTag == 'td':
            #This may span cols, so add additional columns to bridge the span
            numCols = 1
            for tup in attrs:
                if tup[0] == 'colspan':
                    numCols = int(tup[1])
                    break
            self.rowRef += ['']*numCols
            self.colRef = self.rowRef
        else:
            pass

    def handle_endtag(self, endTag):
        if endTag == 'table':
            self.tableRef = None
        elif endTag == 'tr':
            self.rowRef = None
        elif endTag == 'th':
            self.colRef = None
        elif endTag == 'td':
            self.colRef = None
        else:
            pass

    def handle_data(self, data):
        if self.colRef:
            self.colRef[-1]+= data.strip()

    def handle_startendtag(self,startendTag, attrs):
        pass

    def handle_comment(self,data):
        pass

    def get_table(self):
        return self.tableList



class NoaaObsParser(RMParser):
    parserName = "NOAA Observations"  # Your parser name
    parserDescription = "NOAA Observations Data" # A short description of your parser
    parserForecast = False # True if parser provides future forecast data
    parserHistorical = True # True if parser also provides historical data (only actual observed data)
    parserInterval = 6 * 3600             # Your parser running interval in seconds, data will only be mixed in hourly intervals
    parserDebug = False
    parserEnabled = False
    params = {
        "_stationURL" : "https://forecast.weather.gov/data/obhistory/KBDU.html",
        "stationID" : 'KBDU',
        "dailyAccum": True,
        "_lastRain" : '',
        "_lastRainTS": '',
        "_lastTS": ''
    }

    def perform(self):                # The function that will be executed must have this name
        if self.params['stationID']:
            stationID = self.params['stationID']
        else:
            log.error("*** No Station ID")
            self.lastKnownError = "No Station ID"

        
        #NOAA has a bunch of different feeds for the weather data, but only obhistory has rainfall
        # A full listing of stations/urls can be found here: https://forecast.weather.gov/xml/current_obs/index.xml
        stationURL = "https://forecast.weather.gov/data/obhistory/" + stationID + ".html"
        self.params['_stationURL'] = stationURL

        # downloading data from a URL convenience function since other python libraries can be used
        self.getObservations(stationURL)

        if self.parserDebug:
            log.debug(self.result)

    def __parse_time(self, date, time):
        try:
            log_day = int(date)
            log_time = [int(x) for x in time.split(':')]
        except:
            return None

        if self.params['dailyAccum']:
            tsToday = rmCurrentDayTimestamp()
            tsYesterDay = rmDeltaDayFromTimestamp(tsToday, -1)
            today = rmTimestampToDate(tsToday)
            yester = rmTimestampToDate(tsYesterDay)

            #Only update rain for today and yesterday as a daily average
            if(today.day == log_day):
                log_date = today
            elif(yester.day == log_day):
                log_date = yester
            else:
                return None

        else:
            curTime = rmNowDateTime()

            # The date format logged is very annoying... it's just the day of the month.
            # Since the log is only 1 week long, we can't have a date bigger than today unless it's from the previous month.
            month = curTime.month
            day = curTime.day
            year = curTime.year

            #Don't short circuit for just today since NOAA only updates HTML every few hours and we may miss rain
            # in the late evening
            #if day != log_day:
            #    return None

            if day - log_day < 0:
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1

            #Construct a new date with the month/day/time information
            # Rainmachine addValue rounds to the hour, so drop the minutes and we'll accumulate outside
            log_date = datetime(year, month, log_day, log_time[0])


        #convert to our unix timestamp for logging
        #  This is the same method RM uses in rmGetStartOfDay() which matches all the timestamp styles
        timestamp = int(log_date.strftime("%s"))

        return timestamp

    def __parse_precip(self, hr1, hr3, hr6):
        try:
            rain = float(hr1) * 25.4 #i n to mm
            return rain
        except:
            return 0

    def getObservations(self,stationURL):
        d = self.openURL(stationURL)
        parser = NoaaTableParser()
        if d is None:
            log.error("*** Failed to fetch URL")
            self.lastKnownError = "Failed to Fetch"
            return False
        try:
            parser.feed(d.read().decode('utf-8'))
            tree = parser.get_table()
        except:
            log.error("*** Failed to parse response!")
            self.lastKnownError = "Failed to Parse"
            return False

        # It's very likely that all stations generate the same table layout, but just quickly search for 'Date' to find
        #  the correct table
        tableIdx = None
        for tIdx, table in enumerate(tree):
            if len(table) and len(table[0]) and 'Date' == table[0][0]:
                tableIdx = tIdx

        if tableIdx==None:
            log.error("*** No information found in response!")
            self.lastKnownError = "Retrying hourly data retrieval"
            return False


        # Dynamically build a list of column names for indexing
        weatherObs = tree[tableIdx]
        fieldIdx = {}
        for cIdx, col in enumerate(weatherObs[0]):
            colStr = re.split('[^a-zA-Z]',col)
            fieldIdx[colStr[0]] = cIdx

        # Walk our table and build a list of tuples to insert
        #  Skip the first 3 and last 3 rows since that's the headers
        headerLen = len(weatherObs[0])
        rainData = {}
        for row in weatherObs[3:-3]:
            if len(row) == headerLen:
                time = self.__parse_time(row[fieldIdx['Date']],row[fieldIdx['Time']])

                if time:
                    # Need to see how the precipitation is logged for 1/3/6 hr, when rows are ~28min apart
                    #  Update:  It looks like each row is just the rain (inches) for the current interval, so while we query today, just insert the rain
                    #   at the matching timestamp and let the rainmachine parser sum it up for the entire day.
                    rain = self.__parse_precip(row[fieldIdx['Precipitation'] - 2], row[fieldIdx['Precipitation'] - 1],
                                               row[fieldIdx['Precipitation']])

                    if time in rainData:
                        rainData[time] += rain
                    else:
                        rainData[time] = rain

        for k, v in sorted(rainData.items()):
            self.addValue(RMParser.dataType.RAIN, k, v)

            if v > 0:
                self.params['_lastRain'] = v
                self.params['_lastRainTS'] = k
            self.params['_lastTS'] = k
            #log.info("times:%s (%d) Rain:%f"%(rmTimestampToDateAsString(k), k, v))

        # Reset lastKnownError from a previous function call
        self.lastKnownError = ""

        pass



if __name__ == "__main__":
    p = NoaaObsParser()
    p.perform()
