# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from datetime import datetime, timedelta, tzinfo
from math import sin, cos, asin, acos, sqrt

from RMUtilsFramework.rmLogging import log

import time,calendar

ZERO = timedelta(0)

class UTC(tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO
utc = UTC()
utc_t0 = datetime(1970, 1, 1, tzinfo=utc)

def rmYMDToTimestamp(year, month, day):
    try:
        return int(datetime(year, month, day).strftime("%s"))
    except ValueError:
        return int(time.mktime(datetime(year, month, day).timetuple())) # Windows platform doesn't have strftime(%s)

def rmYMDFromTimestamp(timestamp):
    d = datetime.fromtimestamp(timestamp)
    return d.year, d.month, d.day

def rmTimestampToDate(timestamp):
    return datetime.fromtimestamp(timestamp)

def rmTimestampToDateAsString(timestamp, format = None):
    if format:
        return datetime.fromtimestamp(timestamp).strftime(format)
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def rmCurrentTimestampToDateAsString(format = None):
    timestamp = int(time.time())
    if format:
        return datetime.fromtimestamp(timestamp).strftime(format)
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def rmTimestampToUtcDateAsString(timestamp, format = None):
    if format:
        return datetime.utcfromtimestamp(timestamp).strftime(format)
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def rmTimestampFromDateAsString(dateString, format):
    return int(datetime.strptime(dateString, format).strftime("%s"))

def rmTimestampFromDateAsStringWithOffset(dateString):
    # format in form of 2015-04-24T08:00:00-04:00 converted to UTC timestamp
    if dateString is None:
        return None

    try:
        sign =  int(dateString[19:20] + '1')
        (hour, minute) = [int(s) for s in dateString[20:].split(':')]
        offset = sign * (hour * 60 * 60 + minute * 60)
    except:
        return None

    try:
        start_time = datetime.strptime(dateString[:19], "%Y-%m-%dT%H:%M:%S")
        timestamp = int(calendar.timegm(start_time.timetuple())) - offset
    except:
        return None

    return timestamp

def rmTimestampToYearMonthDay(timestamp):
    d = datetime.fromtimestamp(timestamp)
    return d.year, d.month, d.day

def rmNowToYearMonthDay():
    d = datetime.now()
    return d.year, d.month, d.day

def rmNormalizeTimestamp(timestamp):
    return int(datetime.fromtimestamp(timestamp).strftime('%s'))

def rmTimestampToDayOfYear(timestamp):
    if timestamp is None:
        timestamp = rmCurrentDayTimestamp()
    d = datetime.fromtimestamp(timestamp).timetuple()
    return d.tm_yday

def rmNowDateTime():
    return datetime.now()

def rmCurrentTimestamp():
    return int(time.time())

def rmCurrentDayTimestamp():
    return rmGetStartOfDay(int(time.time()))

def rmCurrentMinuteTimestamp():
    timestamp = int(time.time())
    return timestamp - (timestamp % 60)

def rmGetStartOfDay(timestamp):
    tuple = datetime.fromtimestamp(timestamp).timetuple()
    return int(datetime(tuple.tm_year, tuple.tm_mon, tuple.tm_mday).strftime("%s"))

def rmGetStartOfDayUtc(timestamp):
    tuple = datetime.utcfromtimestamp(timestamp).timetuple()
    dt = datetime(tuple.tm_year, tuple.tm_mon, tuple.tm_mday, tzinfo=utc)
    return int((dt-utc_t0).total_seconds())

def rmTimestampIsLeapYear(timestamp):
    d = datetime.fromtimestamp(timestamp)

    #try:
    #    datetime(d.year, 2, 29)
    #    return True
    #except ValueError:
    #    return False

    if d.year % 400 == 0:
        return True
    elif d.year % 100 == 0:
        return False
    elif d.year % 4 == 0:
        return True
    return False

def rmConvertDateStringToFormat(dateString, inputFormat, outputFormat):
    return datetime.strptime(dateString, inputFormat).strftime(outputFormat)

def rmDayRange(startDayTimestamp, numDays):
    d = datetime.fromtimestamp(startDayTimestamp)
    if numDays >=0:
        dateList = [int(time.mktime( (d + timedelta(days=x)).timetuple() )) for x in range(0, numDays)]
    else:
        numDays = -numDays
        dateList = [int(time.mktime( (d - timedelta(days=x)).timetuple() )) for x in range(0, numDays)]
    return  dateList

def rmDeltaDayFromTimestamp(startDayTimeStamp, deltaDays):
    d = datetime.fromtimestamp(startDayTimeStamp)
    if deltaDays < 0:
        d = d - timedelta(days=-deltaDays)
    else:
        d = d + timedelta(days=deltaDays)
    return int(time.mktime(d.timetuple()))

def rmGetNumberOfDaysBetweenTimestamps(startTimestamp, endTimestamp):
    d1 = datetime.fromtimestamp(startTimestamp)
    d2 = datetime.fromtimestamp(endTimestamp)
    delta = d2-d1
    return delta.days

# Sunrise and sunset for specific location and elevation
def computeSuntransitAndDayLenghtForDayTs(ts, lat, lon, elevation):
    ts = rmGetStartOfDayUtc(ts)
    n = julianDayFromTimestamp(ts)
    J = __computeMeanSolarNoon(n, lon)
    M = __computeSolarMeanAnomay(J)
    C = __equationOfTheCenter(M)
    L = __computeEclipticLongitude(M, C)
    Jtr = computeSolarTransit(J, M, L)
    delta = __computeSinSunDeclination(L)
    w0 = computeHourAngle(lat, delta, elevation)
    return Jtr, w0


def rmGetSunsetTimestampForDayTimestamp(ts, lat, lon, elevation):
    Jtr, w0 = computeSuntransitAndDayLenghtForDayTs(ts, lat, -lon, elevation)
    Jset = Jtr+w0/360
    tsJset = julianDayToUTC(Jset)
    return  tsJset


def rmGetSunriseTimestampForDayTimestamp(ts, lat, lon, elevation):
    Jtr, w0 = computeSuntransitAndDayLenghtForDayTs(ts, lat, -lon, elevation)
    Jrise = Jtr-w0/360
    tsJrise = julianDayToUTC(Jrise)
    return  tsJrise

def julianDayFromTimestamp(ts):
    ts = rmGetStartOfDayUtc(ts) + 12*3600
    JD = float(ts)/86400 + 2440587.5
    return JD - 2451545.0 + 0.0008


def julianDayToUTC(JD):
    return (JD - 2440587.5)*86400


def __cosa(degree):
    radian = degree/180*3.14159265359
    return cos(radian)


def __sina(degree):
    radian = degree/180*3.14159265359
    return sin(radian)


def __acosa(x):
    radian = acos(x)
    return radian/3.14159265359*180


def __asina(x):
    radian = asin(x)
    return radian/(3.14159265359)*180



def __computeMeanSolarNoon(jd, wlon):
    J = wlon/360 + jd
    return  J


def __computeSolarMeanAnomay(solarNoon): #degrees
    return (357.5291 + 0.98560028*solarNoon)%360


def __equationOfTheCenter(solarMeanAnomaly): # constant from sine
    M = solarMeanAnomaly
    return 1.9148*__sina(M) + 0.0200*__sina(2*M) + 0.0003*__sina(3*M)


def __computeEclipticLongitude(solarMeanAnomaly, eqCenter): #degrees (it adds a sum a sines)
    L = (solarMeanAnomaly + eqCenter + 180 + 102.9372) % 360
    return L


def computeSolarTransit(meanSolarNoon, solarMeanAnomaly, eclipticLongitude): #substract sinuses from 12 am
    Jtr = 2451545.0 + meanSolarNoon + (0.0053*__sina(solarMeanAnomaly) - 0.0069*__sina(2*eclipticLongitude))
    return Jtr


def __computeSinSunDeclination(L):
    delta = __sina(L)*__sina(23.439 )
    return delta


def computeHourAngle(nlat, sdelta, elevation):
    elevCoef = -2.076*sqrt(elevation)/60
    cosw0 = (__sina(-0.83+elevCoef) - __sina(nlat)*sdelta)/ ( sqrt(1-sdelta*sdelta) * __cosa(nlat))
    return __acosa(cosw0)


def rmNTPFetch(server = "pool.ntp.org", withRequestDrift = False):

    import struct
    from socket import socket, AF_INET, SOCK_DGRAM

    requestPacket = '\x1b' + 47 * '\0'
    startTime = time.time()

    try:
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.settimeout(5)
    except Exception, e:
        log.error("NTPFetch: Can't create socket")
        return None

    try:
        sock.sendto(requestPacket, (server, 123))
        data, ip = sock.recvfrom(1024)
    except Exception, e:
        log.error("NTPFetch: Error receiving data: %s" % e)
        return None

    try:
        if data:
            timestamp = struct.unpack('!12I', data)[10]
            timestamp -= 2208988800L # = date in sec since epoch

            # http://stackoverflow.com/questions/1599060/how-can-i-get-an-accurate-utc-time-with-python
            if withRequestDrift:
                reqTime = time.time() - startTime
                timestamp += reqTime / 2
            return timestamp
    except:
        log.error("NTPFetch: Conversion failed.")
        return None

