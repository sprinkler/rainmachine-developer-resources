from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging
from RMUtilsFramework.rmTimeUtils import * #rmNowDateTime, rmGetStartOfDay, rmCurrentDayTimestamp, rmDeltaDayFromTimestamp, rmCurrentTimestamp

import json
from datetime import datetime
from HTMLParser import HTMLParser
import re
import time
import calendar


class NoaaTableParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        # Keep parser state instance-local so repeated parser runs do not leak previous tables.
        self.tableList = []
        self.tableRef = None
        self.rowRef = None
        self.colRef = None

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
        "stationID" : 'KBDU',
        "dailyAccum": True,
        "_stationURL" : "https://forecast.weather.gov/data/obhistory/KBDU.html",
        "_stationURLFallback" : "ftp://tgftp.nws.noaa.gov/data/observations/metar/stations/KBDU.TXT",
        "useFallbackURL": True,
        "_lastRain" : '',
        "_lastRainTS": '',
        "_lastTS": '',
        "_lastRainDate": '',
        "_lastDate": ''
    }
    defaultParams = params.copy()

    def perform(self):                # The function that will be executed must have this name
        if self.params['stationID']:
            stationID = self.params['stationID']
        else:
            log.error("*** No Station ID")
            self.lastKnownError = "No Station ID"

        
        #NOAA has a bunch of different feeds for the weather data, but only obhistory has rainfall
        # A full listing of stations/urls can be found here: https://forecast.weather.gov/xml/current_obs/index.xml
        stationURL = "https://forecast.weather.gov/data/obhistory/" + stationID + ".html"
        stationURLFallback = "ftp://tgftp.nws.noaa.gov/data/observations/metar/stations/" + stationID + ".TXT"
        self.params['_stationURL'] = stationURL
        self.params['_stationURLFallback'] = stationURLFallback

        # downloading data from a URL convenience function since other python libraries can be used
        self.getObservations(stationURL, stationURLFallback)

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


        # Convert to local unix timestamp using system timezone.
        timestamp = int(time.mktime(log_date.timetuple()))

        return timestamp

    def __parse_precip(self, hr1, hr3, hr6):
        try:
            hr1 = str(hr1).strip()
            if not hr1 or hr1.lower() == 't':
                return 0
            rain = float(hr1) * 25.4 # in to mm
            return rain
        except:
            return 0

    def __find_observation_table(self, tree):
        for table in tree:
            headerBlob = ' '.join([
                str(c).strip().lower()
                for row in table[:6]
                for c in row
                if str(c).strip()
            ])
            if 'date' in headerBlob and 'time' in headerBlob and 'precipitation' in headerBlob:
                return table
        return None

    def __get_precip_indexes(self, weatherObs):
        idx1 = None
        idx3 = None
        idx6 = None

        for row in weatherObs[:6]:
            for cIdx, col in enumerate(row):
                colName = str(col).strip().lower()
                if colName == '1 hr':
                    idx1 = cIdx
                elif colName == '3 hr':
                    idx3 = cIdx
                elif colName == '6 hr':
                    idx6 = cIdx

        # NOAA keeps precip columns at the end; use as fallback if header matching changes.
        if idx1 is None or idx3 is None or idx6 is None:
            return -3, -2, -1

        return idx1, idx3, idx6

    def __add_rain_value(self, timestamp, rain):
        self.addValue(RMParser.dataType.RAIN, timestamp, rain)

        if rain > 0:
            self.params['_lastRain'] = rain
            self.params['_lastRainTS'] = timestamp
            self.params['_lastRainDate'] = rmTimestampToDateAsString(timestamp)
        self.params['_lastTS'] = timestamp
        self.params['_lastDate'] = rmTimestampToDateAsString(timestamp)

    def __parse_metar_fallback(self, fallbackURL):
        d = self.openURL(fallbackURL)
        if d is None:
            return False

        try:
            payload = d.read()
            if not isinstance(payload, str):
                payload = payload.decode('utf-8')
            lines = [line.strip() for line in payload.splitlines() if line.strip()]
            if len(lines) < 2:
                return False

            # Example format:
            # 2026/06/03 04:35
            # KBDU 030435Z AUTO ... RMK AO2 P0001
            obsUTC = datetime.strptime(lines[0], '%Y/%m/%d %H:%M')
            timestamp = int(calendar.timegm(obsUTC.timetuple()))

            metarLine = lines[1]
            match = re.search(r'\bP(\d{4})\b', metarLine)
            rain = 0
            if match:
                rainInches = int(match.group(1)) / 100.0
                rain = rainInches * 25.4

            self.__add_rain_value(timestamp, rain)
            self.lastKnownError = ""
            log.warning("*** NOAA HTTPS fetch failed; using FTP METAR fallback from %s" % fallbackURL)
            return True
        except Exception, e:
            log.error("*** Failed NOAA fallback parse from %s" % fallbackURL)
            log.exception(e)
            return False

    def getObservations(self, stationURL, fallbackURL=None):
        if self.params.get('useFallbackURL', False) and fallbackURL:
            if self.__parse_metar_fallback(fallbackURL):
                return True

        d = self.openURL(stationURL)
        parser = NoaaTableParser()
        if d is None:
            if fallbackURL and self.__parse_metar_fallback(fallbackURL):
                return True
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

        weatherObs = self.__find_observation_table(tree)
        if weatherObs is None:
            log.error("*** No information found in response!")
            self.lastKnownError = "Retrying hourly data retrieval"
            return False

        precip1Idx, precip3Idx, precip6Idx = self.__get_precip_indexes(weatherObs)

        # Walk our table and build a list of tuples to insert
        # NOAA layout can change, so detect data rows by content instead of fixed offsets.
        rainData = {}
        for row in weatherObs:
            if len(row) < 5:
                continue

            dateVal = str(row[0]).strip()
            timeVal = str(row[1]).strip()
            if not dateVal.isdigit() or ':' not in timeVal:
                continue

            time = self.__parse_time(dateVal, timeVal)
            if not time:
                continue

            if len(row) < 3:
                continue

            try:
                rain = self.__parse_precip(row[precip1Idx], row[precip3Idx], row[precip6Idx])
            except:
                rain = self.__parse_precip(row[-3], row[-2], row[-1])

            if time in rainData:
                rainData[time] += rain
            else:
                rainData[time] = rain

        for k, v in sorted(rainData.items()):
            self.__add_rain_value(k, v)
            #log.info("times:%s (%d) Rain:%f"%(rmTimestampToDateAsString(k), k, v))

        # Reset lastKnownError from a previous function call
        self.lastKnownError = ""

        pass



if __name__ == "__main__":
    p = NoaaObsParser()
    p.perform()
