# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmUtils import convertKnotsToMS, convertFahrenheitToCelsius, convertInchesToMM, convertToFloat, convertToInt
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType

import ctypes
import datetime
import os
import socket
import ssl
import struct
import sys
import time
import urllib
import urllib2
from xml.etree import ElementTree as e

# ---------------------------------------------------------------------------
# TLS SNI support for older controllers
#
# Measured on a Mini-8 (Python 2.7.3 / OpenSSL 1.0.1f): graphical.weather.gov
# and api.weather.gov answer normally when the hostname is sent in the TLS
# ClientHello, but fail the handshake through urllib2 because Python 2.7.3 and
# 2.7.8 cannot send SNI (support arrived in 2.7.9 / PEP 466). The NWS edge
# serves its default certificate, the Host does not match, and the connection
# is torn down before the XML is ever requested.
#
# libssl.so IS present and OpenSSL has done SNI since 0.9.8f - only Python
# fails to expose it. This parser loads libssl through ctypes and calls
# SSL_set_tlsext_host_name(), which is SSL_ctrl(ssl, 55, 0, host), before the
# handshake, exactly as curl does. Controllers with a modern Python are
# unaffected - they keep using urllib2 and only fall back to ctypes if it
# fails.
#
# The ctypes path does not verify certificates. Neither did the firmware it
# exists for: 2.7.3's urllib2 never verified, and a 2014 CA bundle cannot
# validate a current chain anyway.
#
# Everything below is additive: perform() is unchanged, because openURL() is
# overridden to use this transport and still returns an object with .read().
# ---------------------------------------------------------------------------

SSL_CTRL_SET_TLSEXT_HOSTNAME = 55   # openssl/ssl.h
TLSEXT_NAMETYPE_host_name    = 0    # openssl/tls1.h
SSL_RETRY_ERRORS = (2, 3, 5)        # WANT_READ, WANT_WRITE, SYSCALL

# Absolute paths: ctypes.util.find_library() returns None on these images,
# there is no ldconfig cache to consult.
SSL_LIBS = ["/usr/lib/libssl.so.1.0.0", "/lib/libssl.so.1.0.0",
            "/usr/lib/libssl.so.1.0.2", "/usr/lib/libssl.so.1.1",
            "/usr/lib/libssl.so", "/system/lib/libssl.so",
            "/system/lib64/libssl.so", "libssl.so.1.0.0", "libssl.so"]
CRYPTO_LIBS = [p.replace("libssl", "libcrypto") for p in SSL_LIBS]


class SNIError(Exception):
    """The ctypes/libssl transport could not complete the request."""


class SSLBinding(object):
    """ctypes binding to the device's libssl, loaded once per process."""

    _instance = None
    _failed = False

    @classmethod
    def get(cls):
        if cls._failed:
            return None
        if cls._instance is None:
            try:
                cls._instance = SSLBinding()
            except Exception, e:
                cls._failed = True
                log.warning("NOAA: libssl unavailable: %s" % e)
                return None
        return cls._instance

    def __init__(self):
        # libcrypto first and with RTLD_GLOBAL so libssl resolves against it.
        self.crypto, _ = self.__load(CRYPTO_LIBS, True)
        self.lib, self.path = self.__load(SSL_LIBS, False)

        s = self.lib
        vp, ci, cl, cc = ctypes.c_void_p, ctypes.c_int, ctypes.c_long, ctypes.c_char_p
        self.method = getattr(s, "SSLv23_client_method", None) or s.TLS_client_method
        self.method.restype = vp

        for name, argtypes, restype in (
                ("SSL_CTX_new",   [vp],             vp),
                ("SSL_CTX_free",  [vp],             None),
                ("SSL_new",       [vp],             vp),
                ("SSL_free",      [vp],             None),
                ("SSL_set_fd",    [vp, ci],         ci),
                ("SSL_ctrl",      [vp, ci, cl, cc], cl),
                ("SSL_connect",   [vp],             ci),
                ("SSL_write",     [vp, cc, ci],     ci),
                ("SSL_read",      [vp, cc, ci],     ci),
                ("SSL_shutdown",  [vp],             ci),
                ("SSL_get_error", [vp, ci],         ci)):
            fn = getattr(s, name)
            fn.argtypes = argtypes
            if restype is not None:
                fn.restype = restype

        # Present in 1.0.x, gone in 1.1.x where initialisation is implicit.
        for name in ("SSL_library_init", "SSL_load_error_strings"):
            try:
                getattr(s, name)()
            except AttributeError:
                pass

    def __load(self, names, asGlobal):
        lastError = None
        for name in names:
            if name.startswith("/") and not os.path.exists(name):
                continue
            try:
                if asGlobal:
                    return ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL), name
                return ctypes.CDLL(name), name
            except Exception, e:
                lastError = e
        raise SNIError(str(lastError))


def dechunkBody(body):
    """Decode a chunked transfer-encoded body."""
    parts = []
    while body:
        newline = body.find("\r\n")
        if newline < 0:
            break
        try:
            size = int(body[:newline].split(";")[0].strip(), 16)
        except ValueError:
            break
        if size == 0:
            break
        parts.append(body[newline + 2:newline + 2 + size])
        body = body[newline + 2 + size + 2:]
    return "".join(parts)


def sniGet(url, timeout, agent, extraHeaders=None):
    """HTTPS GET with TLS SNI via libssl. Returns (status, body)."""
    binding = SSLBinding.get()
    if binding is None:
        raise SNIError("libssl unavailable")

    rest = url.split("://", 1)[1]
    cut  = rest.find("/")
    host = rest[:cut] if cut >= 0 else rest
    path = rest[cut:] if cut >= 0 else "/"

    sock = socket.create_connection((host, 443), timeout)
    # create_connection leaves the socket non-blocking, which makes OpenSSL's
    # blocking calls return WANT_READ immediately. Restore blocking mode and
    # let the kernel enforce the timeout instead.
    sock.setblocking(1)
    try:
        tv = struct.pack("ll", int(timeout), 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, tv)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, tv)
    except Exception:
        pass

    s = binding.lib
    ctx = conn = None
    try:
        ctx = s.SSL_CTX_new(binding.method())
        if not ctx:
            raise SNIError("SSL_CTX_new failed")
        conn = s.SSL_new(ctx)
        if not conn:
            raise SNIError("SSL_new failed")
        if s.SSL_set_fd(conn, sock.fileno()) != 1:
            raise SNIError("SSL_set_fd failed")

        # This single call is the entire point of the ctypes path.
        if s.SSL_ctrl(conn, SSL_CTRL_SET_TLSEXT_HOSTNAME,
                      TLSEXT_NAMETYPE_host_name, host) != 1:
            raise SNIError("cannot set SNI hostname")

        if s.SSL_connect(conn) != 1:
            raise SNIError("handshake failed (err=%d)" % s.SSL_get_error(conn, -1))

        # HTTP/1.1 - HTTP/1.0 draws 426 Upgrade Required from some edges.
        headers = {"Host": host, "User-Agent": agent,
                   "Accept": "application/xml", "Connection": "close"}
        if extraHeaders:
            for k, v in extraHeaders.items():
                headers[k] = v
        request = "GET %s HTTP/1.1\r\n" % path
        for k, v in headers.items():
            request += "%s: %s\r\n" % (k, v)
        request += "\r\n"
        sent = 0
        while sent < len(request):
            n = s.SSL_write(conn, request[sent:], len(request) - sent)
            if n <= 0:
                raise SNIError("SSL_write failed")
            sent += n

        # SSL_read returning <= 0 does not necessarily mean end of stream. On
        # slow hardware it is often WANT_READ, or SYSCALL raised by the
        # SO_RCVTIMEO timer. Treating those as EOF truncates the body and
        # yields invalid XML, which makes refreshes fail at random.
        chunks = []
        buf = ctypes.create_string_buffer(16384)
        deadline = time.time() + timeout
        while True:
            n = s.SSL_read(conn, buf, 16384)
            if n > 0:
                chunks.append(buf.raw[:n])
                continue
            if s.SSL_get_error(conn, n) in SSL_RETRY_ERRORS and time.time() < deadline:
                time.sleep(0.1)
                continue
            break               # ZERO_RETURN, clean close, or a hard error
        data = "".join(chunks)
    finally:
        try:
            if conn:
                s.SSL_shutdown(conn)
                s.SSL_free(conn)
            if ctx:
                s.SSL_CTX_free(ctx)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass

    start = data.find("HTTP/1.")
    if start < 0:
        raise SNIError("no HTTP response")
    data = data[start:]
    try:
        status = int(data.split(" ", 2)[1])
    except Exception:
        raise SNIError("bad status line")

    sep = data.find("\r\n\r\n")
    if sep < 0:
        return status, ""
    head = data[:sep].lower()
    body = data[sep + 4:]

    if "transfer-encoding: chunked" in head:
        body = dechunkBody(body)
    elif "content-length:" in head:
        # Catch a short read here rather than handing a truncated body to
        # ElementTree, so the caller reports the real problem.
        try:
            expected = int(head.split("content-length:")[1].split("\r\n")[0].strip())
            if len(body) < expected:
                raise SNIError("truncated body (%d of %d bytes)" % (len(body), expected))
        except (ValueError, IndexError):
            pass
    return status, body


class SNIResponse(object):
    """Minimal file-like object so existing openURL() callers keep working.

    read() honours the optional size argument because ElementTree.parse()
    consumes the body in 64 KiB chunks, and a read() that ignores the size
    would loop forever on an exhausted buffer.
    """

    def __init__(self, data, status):
        self.data = data
        self.status = status
        self._pos = 0

    def read(self, size=-1):
        if size is None or size < 0:
            result = self.data[self._pos:]
            self._pos = len(self.data)
            return result
        result = self.data[self._pos:self._pos + size]
        self._pos += len(result)
        return result

    def getcode(self):
        return self.status

    def close(self):
        pass


class NOAA(RMParser):
    parserName = "NOAA Parser"
    parserDescription = "North America weather forecast from National Oceanic and Atmospheric Administration"
    parserForecast = True
    parserHistorical = False
    parserEnabled = True
    parserDebug = False
    parserInterval = 6 * 3600
    params = {}

    skippedDays = {} # keep track of incomplete days
    intervalsCache = {} # keep track of intervals in the current day

    #-----------------------------------------------------------------------
    # Transport
    #
    # openURL() is overridden so perform() needs no changes: it still gets
    # back an object with .read(). Controllers whose ssl module can send SNI
    # keep using urllib2 and only fall back to ctypes if it fails; controllers
    # without SNI go straight to the ctypes path, which is the only thing that
    # reaches graphical.weather.gov and api.weather.gov on that firmware.

    agent = "RainMachine v2"
    timeout = 60

    _answered = False
    _sniChecked = False
    _sniAvailable = False

    def hasNativeSNI(self):
        if not NOAA._sniChecked:
            NOAA._sniAvailable = (bool(getattr(ssl, "HAS_SNI", False))
                                  and hasattr(ssl, "SSLContext"))
            NOAA._sniChecked = True
        return NOAA._sniAvailable

    def __viaUrllib(self, url, headers):
        requestHeaders = {"User-Agent": self.agent, "Accept": "application/xml"}
        requestHeaders.update(headers or {})
        request = urllib2.Request(url, headers=requestHeaders)
        try:
            response = urllib2.urlopen(request, timeout=self.timeout)
            return SNIResponse(response.read(), response.getcode())
        except urllib2.HTTPError, e:
            log.warning("NOAA: HTTP %s from %s" % (e.code, self.__safeURL(url)))
        except Exception, e:
            log.warning("NOAA: urllib2 failed: %s" % e)
        return None

    def __viaCtypes(self, url, headers):
        # Embedded hardware drops the occasional handshake or read; one retry
        # turns an intermittent failure into a successful refresh.
        for attempt in (1, 2):
            try:
                status, body = sniGet(url, self.timeout, self.agent, headers)
            except Exception, e:
                if attempt == 1:
                    time.sleep(1)
                    continue
                log.warning("NOAA: libssl transport failed: %s" % e)
                return None
            if status != 200:
                # A status code means the edge and the service answered, so the
                # SNI handshake worked and this result is definitive. Falling
                # back to urllib2 would only produce a misleading handshake
                # failure from a stack that cannot send SNI in the first place.
                log.warning("NOAA: HTTP %s from %s" % (status, self.__safeURL(url)))
                self._answered = True
                return None
            return SNIResponse(body, status)
        return None

    def __safeURL(self, url):
        at = url.find("token=")
        return url if at < 0 else url[:at] + "token=***"

    def openURL(self, url, params=None, encodeParameters=True, headers={}):
        if params:
            query = urllib.urlencode(params) if encodeParameters else params
            url = "?".join([url, query])

        binding = SSLBinding.get()
        log.debug("NOAA: python=%s sni=%s libssl=%s url=%s"
                  % (sys.version.split()[0],
                     "yes" if self.hasNativeSNI() else "no",
                     binding.path if binding else "none",
                     self.__safeURL(url)))

        self._answered = False
        order = ([self.__viaUrllib, self.__viaCtypes] if self.hasNativeSNI()
                 else [self.__viaCtypes, self.__viaUrllib])
        for transport in order:
            try:
                response = transport(url, headers)
            except Exception:
                response = None
            if response is not None:
                return response
            if self._answered:      # definitive HTTP status; do not retry
                break

        if not (self.hasNativeSNI() or SSLBinding.get() is not None):
            self.lastKnownError = ("Error: no SNI-capable transport on this device - "
                                   "cannot reach NOAA services")
        else:
            self.lastKnownError = "Error: request failed on every available transport"
        log.error(self.lastKnownError)
        return None

    def isEnabledForLocation(self, timezone, lat, long):
        if NOAA.parserEnabled and timezone:
            return timezone.startswith("America") or timezone.startswith("US")
        return False

    def perform(self):
        s = self.settings

        # Order is important
        urls = [
            {
                "host": "https://noaa.rainmachine.com",
                "headers": {"Host": "graphical.weather.gov"},
                "params": []
            },
            {
                "host": "https://noaa.rainmachine.com",
                "headers": {"Host": "graphical.weather.gov"},
                "params": []
            },
            {
                "host": "https://forecast.rainmachine.com",
                "headers": {},
                "params": [("token", "px808345forc")]
            },
            {
                "host": "https://graphical.weather.gov",
                "headers": {},
                "params": []
            },
        ]

        hourlyPath = "/xml/sample_products/browser_interface/ndfdXMLclient.php"
        dailyPath = "/xml/sample_products/browser_interface/ndfdBrowserClientByDay.php"

        baseParams = [
           ("lat", s.location.latitude),
           ("lon", s.location.longitude)
        ]

        # baseParams = [
        #    ("lat", "27"),
        #    ("lon", "-80")
        # ]

        hourlyParams = [
            ("product", "time-series"),
            ("begin", datetime.date.today().strftime("%Y-%m-%d")),
            ("Unit", "e"),
            ("maxt", "maxt"),
            ("mint", "mint"),
            ("temp", "temp"),
            ("qpf", "qpf"),
            ("dew", "dew"),
            ("pop12", "pop12"),
            ("wspd", "wspd"),
            ("rh", "rh"),
            ("maxrh", "maxrh"),
            ("minrh", "minrh")
        ]

        dailyParams = [
            ("startDate", datetime.date.today().strftime("%Y-%m-%d")),
            #("endDate", (datetime.date.today() + datetime.timedelta(6)).strftime("%Y-%m-%d")),
            ("format", "24 hourly"),
            ("numDays", 6),
            ("Unit", "e")
        ]

        baseHeaders = {"User-Agent": "RainMachine v2"}

        hasHourly = False
        hasDaily = False

        for url in urls:
            hourlyURL = url["host"] + hourlyPath
            dailyUrl = url["host"] + dailyPath
            urlHourlyParams = baseParams + hourlyParams + url["params"]
            urlDailyParams = baseParams + dailyParams + url["params"]
            url["headers"].update(baseHeaders)

            if not hasHourly:
                log.info("Fetching Hourly data from %s" % hourlyURL)
                hasHourly = self.getHourlyData(hourlyURL, urlHourlyParams, url["headers"])

            if not hasDaily:
                log.info("Fetching Daily data from %s " % dailyUrl)
                hasDaily = self.getDailyData(dailyUrl, urlDailyParams, url["headers"])

            if hasHourly and hasDaily:
                break

        # If we didn't get Hourly data we consider a fail and retry the whole parser operation.
        # We remove any values obtained by daily call so we can trigger parser retry
        if not hasHourly:
            self.clearValues()

        if self.parserDebug:
            log.debug(self.result)

        self.skippedDays = {}

        # Dump existing cache for today
        if self.parserDebug:
            todayTimestamp = rmCurrentDayTimestamp()
            for cacheKey in self.intervalsCache:
                log.info("%s CACHED %s:" % (rmTimestampToDateAsString(todayTimestamp), cacheKey))
                if todayTimestamp in self.intervalsCache[cacheKey]:
                    for entry in self.intervalsCache[cacheKey][todayTimestamp]:
                        v = self.intervalsCache[cacheKey][todayTimestamp][entry]
                        log.info("\t %s: %s" % (rmTimestampToDateAsString(entry), v))


    #-----------------------------------------------------------------------------------------------
    #
    # Get hourly data.
    #
    def getHourlyData(self, URL, URLParams, headers):

        d = self.openURL(URL, URLParams, headers=headers)
        if d is None:
            return False
        try:
            tree = e.parse(d)
        except:
            return False

        #tree = e.parse("/tmp/noaa-fl-2019-06-04-1.xml")

        if tree.getroot().tag == 'error':
            log.error("*** No hourly information found in response!")
            self.lastKnownError = "Retrying hourly data retrieval"
            tree.getroot().clear()
            del tree
            tree = None
            return False

        # Reset lastKnownError from a previous function call
        self.lastKnownError = ""

        # We get them in English units need in Metric units

        # 2019-06-01: If we send that weather properties we want (qpf=qpf&mint=mint) in request URL NOAA response forgets
        # past hours in current day resulting in a forecast requested at the end of the day
        # having null/0 qpf forgetting the older values which could had more qpf so we need to process QPF first and
        # determine which entries don't have full days with qpf reported (especially current day) then completely skip
        # this day for the rest of the weather properties so we don't have a forecast entry with null/0 qpf

        # Algorithm allows multiple partial days to be skipped because incomplete but we currently only skip today

        # QPF needs to be the first tag parsed to build the skippedDays structure
        qpf = self.__parseWeatherTag(tree, 'precipitation', 'liquid', skippedDays=self.skippedDays, addToSkippedDays=True)
        qpf = convertInchesToMM(qpf)

        maxt = self.__parseWeatherTag(tree, 'temperature', 'maximum', skippedDays=self.skippedDays)
        maxt = convertFahrenheitToCelsius(maxt)

        mint = self.__parseWeatherTag(tree, 'temperature', 'minimum', useStartTimes=False, skippedDays=self.skippedDays) # for mint we want the end-time to be saved in DB
        mint = convertFahrenheitToCelsius(mint)

        temp = self.__parseWeatherTag(tree, 'temperature', 'hourly', skippedDays=self.skippedDays)
        temp = convertFahrenheitToCelsius(temp)

        dew = self.__parseWeatherTag(tree, 'temperature', 'dew point', skippedDays=self.skippedDays)
        dew = convertFahrenheitToCelsius(dew)

        wind = self.__parseWeatherTag(tree, 'wind-speed', 'sustained', skippedDays=self.skippedDays)
        wind = convertKnotsToMS(wind)

        # These are as percentages
        pop = self.__parseWeatherTag(tree, 'probability-of-precipitation', '12 hour', skippedDays=self.skippedDays)
        pop = convertToInt(pop)

        humidity = self.__parseWeatherTag(tree, 'humidity', 'relative', skippedDays=self.skippedDays)
        humidity = convertToFloat(humidity)

        minHumidity = self.__parseWeatherTag(tree, 'humidity', 'minimum relative', skippedDays=self.skippedDays)
        minHumidity = convertToFloat(minHumidity)

        maxHumidity = self.__parseWeatherTag(tree, 'humidity', 'maximum relative', skippedDays=self.skippedDays)
        maxHumidity = convertToFloat(maxHumidity)

        if self.parserDebug:
            tree.write('noaa-' + str(rmTimestampToDateAsString(rmCurrentTimestamp())) + ".xml")

        tree.getroot().clear()
        del tree
        tree = None

        # Save
        self.addValues(RMParser.dataType.MINTEMP, mint)
        self.addValues(RMParser.dataType.MAXTEMP, maxt)
        self.addValues(RMParser.dataType.TEMPERATURE, temp)
        self.addValues(RMParser.dataType.QPF, qpf)
        self.addValues(RMParser.dataType.DEWPOINT, dew)
        self.addValues(RMParser.dataType.WIND, wind)
        self.addValues(RMParser.dataType.POP, pop)
        self.addValues(RMParser.dataType.RH, humidity)
        self.addValues(RMParser.dataType.MINRH, minHumidity)
        self.addValues(RMParser.dataType.MAXRH, maxHumidity)

        return True

    #-----------------------------------------------------------------------------------------------
    #
    # Get daily data.
    #
    def getDailyData(self, URLDaily, URLParams, headers):
        d = self.openURL(URLDaily, URLParams, headers=headers)
        try:
            tree = e.parse(d)
        except:
            return False

        if tree.getroot().tag == 'error':
            log.error("*** No daily information found in response!")
            self.lastKnownError = "Retrying daily brief"
            tree.getroot().clear()
            del tree
            tree = None
            return False

        #tree = e.parse("/tmp/noaa-fl-2019-06-04-daily-1.xml")

        # Reset lastKnownError from a previous function call
        self.lastKnownError = ""

        conditions = self.__parseWeatherTag(tree, 'conditions-icon', 'forecast-NWS', 'icon-link', skippedDays=self.skippedDays)
        parsedConditions = []

        for c in conditions:
            if c and len(c) >= 2:
                try:
                    cv = self.conditionConvert(c[1].rsplit('.')[-2].rsplit('/')[-1])
                except:
                    cv = RMWeatherConditions.Unknown

                parsedConditions.append((c[0], cv))

        tree.getroot().clear()
        del tree
        tree = None

        self.addValues(RMParser.dataType.CONDITION, parsedConditions)

        return True


    def __parseDateTime(self, str, roundToHour = True):
        #NOAA reports in location local time needs UTC conversion
        timestamp = rmTimestampFromDateAsStringWithOffset(str)
        if timestamp is None:
            return None

        if roundToHour:
            return timestamp - (timestamp % 3600)
        else:
            return timestamp

    def __parseTimeLayout(self, tree, key, useStartTimes = True):
        found = False
        validDates = []

        # We can index by using "start-valid-time" or by "end-valid-time"
        if useStartTimes:
            dateTagName =  "start-valid-time"
        else:
            dateTagName =  "end-valid-time"

        for timeElement in tree.getroot().getiterator(tag = "time-layout"):
            for timeData in timeElement.getchildren():
                if timeData.tag == "layout-key" and timeData.text == key:
                    found = True
                elif timeData.tag == dateTagName and found:
                    validDates.append(self.__parseDateTime(timeData.text))

            if found:
                break


        return validDates

    # skippedDays will hold the days skipped by other entries (qpf, temp).
    def __parseWeatherTag(self, tree, tag, type, subtag = "value", useStartTimes = True, typeConvert = None, skippedDays = {}, addToSkippedDays = False):
        values = []
        forecastTimes = []
        timeLayoutKey = None
        cacheKey = tag + type

        todayTimestamp = rmCurrentDayTimestamp()
        maxDayTimestamp = todayTimestamp + globalSettings.parserDataSizeInDays * 86400

        # We start a new current day
        if cacheKey not in self.intervalsCache or todayTimestamp not in self.intervalsCache[cacheKey]:
            self.intervalsCache[cacheKey] = {} # forget older days
            self.intervalsCache[cacheKey][todayTimestamp] = {}

        # Build forecast time intervals list and values list
        for w in tree.getroot().getiterator(tag = tag):
            if w.attrib['type'] != type:
                continue

            timeLayoutKey = w.attrib['time-layout']
            forecastTimes = self.__parseTimeLayout(tree, timeLayoutKey, useStartTimes=useStartTimes)

            for wval in w.getiterator(tag = subtag):
                try:
                    val = wval.text
                    if typeConvert == 'int':
                        val = int(val)
                    if typeConvert == 'float':
                        val = float(val)
                except:
                    val = None

                values.append(val)

        result = zip(forecastTimes, values)
        result.sort(key=lambda z: z[0]) # Sort by timestamp

        # If we don't have 'precipitation' for a full 'today' skip all weather properties for today unless we have something cached
        # Otherwise allow partial day weather properties to be saved even if we don't have a cache of them
        # In other words: If we have full 'today' precipitation allow other partial entries if not forget entire day
        tmpresult = []
        lastDay = None
        skipDay = None

        for z in result:
            day = rmGetStartOfDay(z[0])
            if day in skippedDays:
                log.debug("%s %s day %s in skippedDays skipping" % (tag, type, rmTimestampToDateAsString(day)))
                continue

            startDate = rmTimestampToDate(z[0])
            startHour = startDate.hour

            if todayTimestamp > z[0]:
                log.info("%s %s: reject date %s as it's in the past" % (tag, type, rmTimestampToDateAsString(z[0])))
                continue

            if z[0] >= maxDayTimestamp:
                log.debug("%s %s: reject date %s as it's over the max parser day: %s" % (tag, type, rmTimestampToDateAsString(z[0]), rmTimestampToDateAsString(maxDayTimestamp)))
                continue

            # Check for incomplete days
            if lastDay is None or lastDay < day:
                skipDay = None
                lastDay = day
                log.debug("%s %s: found new day: %s - %s" % (tag, type, rmTimestampToDateAsString(day), rmTimestampToDateAsString(lastDay)))
                # Is this a day with partial data not starting at the beginning of day ?
                if startHour > 10:
                    if day == todayTimestamp: # Limit to today
                        if not self.intervalsCache[cacheKey][todayTimestamp]: # Only if no cache
                            skipDay = day

            # Build skippedDays list
            # Save to skipped days so we can skip for all other weather propeties that will be parsed after
            if day == skipDay:
                # Allow adding partial entries if they aren't already in skippedDays for entries have addToSkippedDays = False
                if addToSkippedDays:
                    skippedDays[skipDay] = True
                    log.info("\t%s %s day: %s starting with hour %s (local) skipping with addToSkippedDays..." % (tag, type, rmTimestampToDateAsString(day), startHour))
                    continue

            # Cache: Update with new value. Older intervals that aren't in current result have their cached values
            if day == todayTimestamp:
                self.intervalsCache[cacheKey][todayTimestamp][z[0]] = z[1]
                log.debug("%s Added interval head %s cache with value: %s" % (cacheKey, rmTimestampToDateAsString(z[0]), z[1]))

            if self.parserDebug:
                log.info("Adding %s: %s for %s" % (cacheKey, z[1], rmTimestampToDateAsString(z[0])))
            tmpresult.append(z)


        # Cache: Add cache entries that don't exist to the tmpresult
        # This way we will still have in latest forecastID the data that was retrieved by other parsers runs
        # on this day
        for entry in self.intervalsCache[cacheKey][todayTimestamp]:
            alreadyIn = False
            for z in tmpresult:
                if entry == z[0]:
                    alreadyIn = True
                    break
            if not alreadyIn:
                v = self.intervalsCache[cacheKey][todayTimestamp][entry]
                log.debug("Adding from Cache: %s: %s for %s" % (cacheKey, v, rmTimestampToDateAsString(entry)))
                tmpresult.append((entry, v))

        return tmpresult


    def conditionConvert(self, conditionStr):
        if 'bkn' in conditionStr:
            return RMParser.conditionType.MostlyCloudy
        elif 'skc' in conditionStr:
            return RMParser.conditionType.Fair
        elif 'few' in conditionStr:
            return RMParser.conditionType.FewClouds
        elif 'sct' in conditionStr:
            return RMParser.conditionType.PartlyCloudy
        elif 'ovc' in conditionStr:
            return RMParser.conditionType.Overcast
        elif 'fg' in conditionStr:
            return  RMParser.conditionType.Fog
        elif 'smoke' in conditionStr:
            return  RMParser.conditionType.Smoke
        elif 'fzra' in conditionStr:
            return  RMParser.conditionType.HeavyFreezingRain
        elif 'ip' in conditionStr:
            return  RMParser.conditionType.IcePellets
        elif 'mix' in conditionStr:
            return  RMParser.conditionType.FreezingRain
        elif 'raip' in conditionStr:
            return  RMParser.conditionType.RainIce
        elif 'rasn' in conditionStr:
            return  RMParser.conditionType.RainSnow
        elif 'shra' in conditionStr:
            return  RMParser.conditionType.RainShowers
        elif 'tsra' in conditionStr:
            return  RMParser.conditionType.Thunderstorm
        elif 'sn' in conditionStr:
            return  RMParser.conditionType.Snow
        elif 'wind' in conditionStr:
            return  RMParser.conditionType.Windy
        elif 'shwrs' in conditionStr:
            return  RMParser.conditionType.ShowersInVicinity
        elif 'fzrara' in conditionStr:
            return  RMParser.conditionType.HeavyFreezingRain
        elif 'hi_tsra' in conditionStr:
            return  RMParser.conditionType.ThunderstormInVicinity
        elif 'ra1' in conditionStr:
            return  RMParser.conditionType.LightRain
        elif 'ra' in conditionStr:
            return  RMParser.conditionType.HeavyRain
        elif 'nsvrtsra' in conditionStr:
            return  RMParser.conditionType.FunnelCloud
        elif 'dust' in conditionStr:
            return  RMParser.conditionType.Dust
        elif 'mist' in conditionStr:
            return  RMParser.conditionType.Haze
        elif 'hot' in conditionStr:
            return  RMParser.conditionType.Hot
        elif 'cold' in conditionStr:
            return  RMParser.conditionType.Cold
        else:
            return  RMParser.conditionType.Unknown


if __name__ == "__main__":
    parser = NOAA()
    parser.perform()