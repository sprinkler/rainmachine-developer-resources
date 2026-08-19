# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmNowDateTime, rmGetStartOfDay, rmCurrentDayTimestamp, rmDeltaDayFromTimestamp
from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType
import ctypes
import json
import os
import socket
import ssl
import struct
import sys
import time
import urllib
import urllib2


# ---------------------------------------------------------------------------
# TLS SNI support for older controllers
#
# api.weather.com sits behind a CDN that requires TLS SNI: the hostname must
# appear in the TLS ClientHello and match the HTTP Host header. Controllers on
# Python 2.7.3 / 2.7.8 have an ssl module that cannot send SNI at all (support
# arrived in 2.7.9 / PEP 466), so the edge serves its default certificate, sees
# a Host it does not cover, and answers HTTP 421 Misdirected Request before the
# API is ever reached. No API key or station setting can work around it.
#
# Shelling out to a downloader is not an option on that hardware: no curl, no
# openssl binary, and BusyBox wget has no TLS. libssl.so IS present though, and
# OpenSSL has supported SNI since 0.9.8f - only Python fails to expose it. So
# the parser loads libssl through ctypes and calls SSL_set_tlsext_host_name(),
# which is SSL_ctrl(ssl, 55, 0, host), before the handshake, exactly as curl
# does. Measured on Mini-8 (2.7.3 / OpenSSL 1.0.1f) and Touch HD-16 (2.7.8 /
# 1.0.1e): a URL that returns 421 through urllib2 returns a normal API reply
# through this path. Controllers with a modern Python are unaffected - they
# keep using urllib2 and only fall back to ctypes if that fails.
#
# The ctypes path does not verify certificates. Neither did the firmware it
# exists for: 2.7.3's urllib2 never verified, and a 2014 CA bundle cannot
# validate a current chain anyway.
#
# Everything below is additive: the parser's own request code is unchanged,
# because openURL() is overridden to use this transport and still returns an
# object with .read().
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
                log.warning("WUnderground: libssl unavailable: %s" % e)
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


def sniGet(url, timeout, agent):
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
        request = ("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\n"
                   "Accept: */*\r\nConnection: close\r\n\r\n" % (path, host, agent))
        sent = 0
        while sent < len(request):
            n = s.SSL_write(conn, request[sent:], len(request) - sent)
            if n <= 0:
                raise SNIError("SSL_write failed")
            sent += n

        # SSL_read returning <= 0 does not necessarily mean end of stream. On
        # slow hardware it is often WANT_READ, or SYSCALL raised by the
        # SO_RCVTIMEO timer. Treating those as EOF truncates the body and
        # yields invalid JSON, which makes refreshes fail at random.
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
        # json.loads(), so the caller reports the real problem.
        try:
            expected = int(head.split("content-length:")[1].split("\r\n")[0].strip())
            if len(body) < expected:
                raise SNIError("truncated body (%d of %d bytes)" % (len(body), expected))
        except (ValueError, IndexError):
            pass
    return status, body


class SNIResponse(object):
    """Minimal file-like object so existing openURL() callers keep working."""

    def __init__(self, data, status):
        self.data = data
        self.status = status

    def read(self):
        return self.data

    def getcode(self):
        return self.status

    def close(self):
        pass



class WUnderground(RMParser):
    parserName = "WUnderground Parser"
    parserDescription = "Global weather service with personal weather station access from Weather Underground"
    parserForecast = True
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600

    # headers for retrival method of nearby stations and station data when we have no key
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'}

    params = {"apiKey" : None
              , "useCustomStation" : False
              , "customStationName": None
              , "_nearbyStationsIDList": []
              , "_airportStationsIDList": []
              , "_apiForecastDays" : 5}

    apiLocationURL = 'https://api.weather.com/v3/location/near?'
    apiStationSummaryURL = 'https://api.weather.com/v2/pws/dailysummary/7day?'
    apiStationCurrentURL = 'https://api.weather.com/v2/pws/observations/current?'
    apiForecastURL = 'https://api.weather.com/v3/wx/forecast/daily/' + str(params["_apiForecastDays"]) + 'day'

    apiURL = None
    jsonResponse = None

    #-----------------------------------------------------------------------
    # Transport
    #
    # openURL() is overridden so none of the request code below needs to
    # change: it still receives an object with .read(). Controllers whose ssl
    # module can send SNI keep using urllib2 and only fall back to ctypes if
    # that fails; controllers without SNI go straight to the ctypes path,
    # which is the only thing that reaches api.weather.com on that firmware.

    agent = "RainMachine-WUnderground/1.0"
    timeout = 60

    _answered = False
    _sniChecked = False
    _sniAvailable = False

    def hasNativeSNI(self):
        if not WUnderground._sniChecked:
            WUnderground._sniAvailable = (bool(getattr(ssl, "HAS_SNI", False))
                                          and hasattr(ssl, "SSLContext"))
            WUnderground._sniChecked = True
        return WUnderground._sniAvailable

    def __safeURL(self, url):
        at = url.find("apiKey=")
        return url if at < 0 else url[:at] + "apiKey=***"

    def __viaUrllib(self, url, agent):
        request = urllib2.Request(url, headers={"User-Agent": agent, "Accept": "*/*"})
        try:
            response = urllib2.urlopen(request, timeout=self.timeout)
            return SNIResponse(response.read(), response.getcode())
        except urllib2.HTTPError, e:
            log.warning("WUnderground: HTTP %s from %s" % (e.code, self.__safeURL(url)))
        except Exception, e:
            log.warning("WUnderground: urllib2 failed: %s" % e)
        return None

    def __viaCtypes(self, url, agent):
        # Embedded hardware drops the occasional handshake or read; one retry
        # turns an intermittent failure into a successful refresh.
        for attempt in (1, 2):
            try:
                status, body = sniGet(url, self.timeout, agent)
            except socket.gaierror, e:
                log.warning("WUnderground: cannot resolve host: %s" % e)
                return None
            except Exception, e:
                if attempt == 1:
                    time.sleep(1)
                    continue
                log.warning("WUnderground: libssl transport failed: %s" % e)
                return None
            if status != 200:
                # A status code means the CDN and the API answered, so the
                # SNI handshake worked and this result is definitive.
                # Falling back to urllib2 would only produce a misleading
                # 421 from a stack that cannot send SNI in the first place.
                log.warning("WUnderground: HTTP %s from %s" % (status, self.__safeURL(url)))
                self._answered = True
                return None
            return SNIResponse(body, status)
        return None

    def openURL(self, url, params = None, encodeParameters = True, headers = {}):
        if params:
            query = urllib.urlencode(params) if encodeParameters else params
            url = "?" . join([url, query])

        agent = headers.get("User-Agent", self.agent)
        binding = SSLBinding.get()
        log.debug("WUnderground: python=%s sni=%s libssl=%s url=%s"
                  % (sys.version.split()[0],
                     "yes" if self.hasNativeSNI() else "no",
                     binding.path if binding else "none",
                     self.__safeURL(url)))

        self._answered = False
        order = ([self.__viaUrllib, self.__viaCtypes] if self.hasNativeSNI()
                 else [self.__viaCtypes, self.__viaUrllib])
        for transport in order:
            try:
                response = transport(url, agent)
            except Exception:
                response = None
            if response is not None:
                return response
            if self._answered:      # definitive HTTP status; do not retry
                break

        if not (self.hasNativeSNI() or SSLBinding.get() is not None):
            self.lastKnownError = ("Error: no SNI-capable transport on this device - "
                                   "cannot reach api.weather.com")
        else:
            self.lastKnownError = "Error: Can not open url"
        log.error(self.lastKnownError)
        return None

    def isEnabledForLocation(self, timezone, lat, long):
        return WUnderground.parserEnabled

    def perform(self):
        self.params["_nearbyStationsIDList"] = []
        self.params["_airportStationsIDList"] = []
        self.lastKnownError = ""
        apiKey = self.params.get("apiKey", None)
        useCustomStation = self.params.get("useCustomStation", False)
        stationName = self.params.get("customStationName")

        hasForecastData = False
        hasStationData = False
        noAPIKey = apiKey is None or not apiKey or not isinstance(apiKey, str)

        if noAPIKey:
            self.getNearbyStationsNoKey()
        else:
            self.getNearbyPWSStationsWithKey(apiKey)
            self.getNearbyAirportStationsWithKey(apiKey)
            hasForecastData = self.getForecastWithKey(apiKey)

        noStationName = stationName is None or not stationName or not isinstance(stationName, str)

        if useCustomStation:
            if stationName is None or not stationName or not isinstance(stationName, str):
                self.lastKnownError = "Warning: Use Nearby Stations is enabled but no station name specified."
                log.error(self.lastKnownError)
            else:
                # Blank entries are skipped. A stray comma leaves an empty
                # name that the API answers with HTTP 400, and the settings UI
                # does not always allow the field to be edited back.
                self.arrStationNames = [n.strip() for n in stationName.split(",") if n.strip()]
                for stationName in self.arrStationNames:
                    if noAPIKey:
                        hasStationData = self.getStationDataNoKey(stationName)
                    else:
                        hasStationData = self.getStationDataWithKey(apiKey, stationName)

                    if hasStationData:  # we only get the first one that responds others are for fallback
                        break

                if not hasStationData:
                    self.lastKnownError = "Warning: No observed data received from stations."
                    if noAPIKey:
                        self.lastKnownError = "Error: No observed data received from stations."
                    log.error(self.lastKnownError)
                else:
                    # A later success supersedes an earlier candidate's error;
                    # without this the UI keeps showing the failed attempt.
                    self.lastKnownError = ""
                    log.info("WUnderground: station data retrieved for %s" % stationName)

        if not hasForecastData and not noAPIKey:
            self.lastKnownError = "Warning: No Forecast data received."
            if not hasStationData:
                self.lastKnownError = "Error: No forecast or station data received."
            log.error(self.lastKnownError)
        else:
            log.info("WUnderground: forecast data retrieved.")


    def getNearbyPWSStationsWithKey(self, apiKey):
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        stationsURL = self.apiLocationURL + 'geocode=' + str(llat) + ',' + str(llon) + '&product=pws&format=json&apiKey=' + str(apiKey)
        try:
            d = self.openURL(stationsURL)
            if d is None:
                self.lastKnownError = "Cannot download nearby pws stations"
                log.error(self.lastKnownError)
            stationsData = d.read()
            stations = json.loads(stationsData)
            self.parseNearbyStationsWithKey(stations)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get nearby pws stations"
            log.error(self.lastKnownError)
            return

    def getNearbyAirportStationsWithKey(self, apiKey):
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        stationsURL = self.apiLocationURL + 'geocode=' + str(llat) + ',' + str(llon) + '&product=airport&format=json&apiKey=' + str(apiKey)
        try:
            d = self.openURL(stationsURL)
            if d is None:
                self.lastKnownError = "Error: Cannot download nearby airport stations"
                log.error(self.lastKnownError)
            stationsData = d.read()
            stations = json.loads(stationsData)
            self.parseNearbyStationsWithKey(stations)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get airport stations"
            log.error(self.lastKnownError)
            return

    def parseNearbyStationsWithKey(self, stationsData):
        location = stationsData['location']
        arrStationId = location.get('stationId', None)
        pws = True
        if arrStationId is None:
            pws = False
            arrStationId = location.get('icaoCode', None)

        arrStationLat = location['latitude']
        arrStationLon = location['longitude']
        arrStationDistance = location['distanceKm']

        arrStations = []
        for index, stationId in enumerate(arrStationId):
            if stationId is None:
                continue
            arrStations.append({'id': stationId, 'lat': arrStationLat[index], 'lon': arrStationLon[index], 'distance': arrStationDistance[index]})
        arrStations = sorted(arrStations, key=lambda k: k['distance'])

        for stationDict in arrStations:
            if pws:
                self.params["_nearbyStationsIDList"].append(stationDict['id'] +  " (" + str(round(stationDict['distance'],1)) + "km" + "; lat=" +
                                                str(round(stationDict['lat'], 2)) + ", lon=" + str(round(stationDict['lon'], 2)) + ")")
            else:
                self.params["_airportStationsIDList"].append(
                    stationDict['id'] + " (" + str(round(stationDict['distance'], 1)) + "km" + "; lat=" +
                    str(round(stationDict['lat'], 2)) + ", lon=" + str(round(stationDict['lon'], 2)) + ")")

    def getStationDataWithKey(self, apiKey, stationName):
        observationURL = self.apiStationSummaryURL + 'stationId=' + str(stationName) + '&format=json&units=m&apiKey=' + str(apiKey)
        try:
            d = self.openURL(observationURL)
            if d is None:
                self.lastKnownError = "Cannot download station data"
                log.error(self.lastKnownError)
                return False
            stationData = d.read()
            observations = json.loads(stationData)
            return self.parseStationDataWithKey(observations)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get station data"
            log.error(self.lastKnownError)
            return False

    def parseStationDataWithKey(self, jsonData):
        # daily summary for yesterday
        tsToday = rmCurrentDayTimestamp()
        tsYesterDay = rmDeltaDayFromTimestamp(tsToday, -1)
        l = RMWeatherDataLimits()
        hasDataAdded = False
        try:
            dailysummary = jsonData['summaries']
            for observation in dailysummary:
                tsDay = observation.get('epoch', None)
                tsDay = rmGetStartOfDay(tsDay)

                temperature = self.__toFloat(observation['metric']['tempAvg'])
                mintemp = self.__toFloat(observation['metric']['tempLow'])
                maxtemp = self.__toFloat(observation['metric']['tempHigh'])
                rh = self.__toFloat(observation["humidityAvg"])
                minrh = self.__toFloat(observation["humidityLow"])
                maxrh = self.__toFloat(observation["humidityHigh"])
                dewpoint = self.__toFloat(observation['metric']["dewptAvg"])
                wind = self.__toFloat(observation['metric']["windspeedAvg"])
                if wind is not  None:
                     wind = wind / 3.6  # converted from kmetersph to mps

                maxpressure = self.__toFloat(observation['metric']["pressureMax"])
                minpressure = self.__toFloat(observation['metric']["pressureMin"])

                if maxpressure is not None:
                    maxpressure = l.sanitize(RMWeatherDataType.PRESSURE, maxpressure / 10.0)  # converted to from hpa to kpa

                if minpressure is not None:
                    minpressure = l.sanitize(RMWeatherDataType.PRESSURE, minpressure / 10.0)

                pressure = None
                if maxpressure is not None and minpressure is not None:
                    pressure = (maxpressure + minpressure) / 2.0

                rain = self.__toFloat(observation['metric']["precipTotal"])

                if tsDay == tsYesterDay:
                    self.addValue(RMParser.dataType.TEMPERATURE, tsDay, temperature, False)
                    self.addValue(RMParser.dataType.MINTEMP, tsDay, mintemp, False)
                    self.addValue(RMParser.dataType.MAXTEMP, tsDay, maxtemp, False)
                    self.addValue(RMParser.dataType.RH, tsDay, rh, False)
                    self.addValue(RMParser.dataType.MINRH, tsDay, minrh, False)
                    self.addValue(RMParser.dataType.MAXRH, tsDay, maxrh, False)
                    self.addValue(RMParser.dataType.WIND, tsDay, wind, False)
                    self.addValue(RMParser.dataType.RAIN, tsDay, rain, False)
                    self.addValue(RMParser.dataType.DEWPOINT, tsDay, dewpoint, False)
                    self.addValue(RMParser.dataType.PRESSURE, tsDay, pressure, False)
                    hasDataAdded = True
                elif tsDay == tsToday:
                    # For today data we only add RAIN which won't overwrite any forecast
                    # We add it at start of day since this entry should be updated at each parser run
                    # otherwise mixer will sum it up
                    self.addValue(RMParser.dataType.RAIN, tsDay, rain, False)
                    hasDataAdded = True
            return hasDataAdded
        except:
            self.lastKnownError = "Warning: Failed to get yesterday data summary"
            log.info(self.lastKnownError)
            return False

    def getStationDataCurrentWithKey(self, apiKey, stationName): # method for current observation
        observationURL = self.apiStationCurrentURL + 'stationId=' + str(stationName) + '&format=json&units=m&apiKey=' + str(apiKey)
        try:
            d = self.openURL(observationURL)
            if d is None:
                self.lastKnownError = "Cannot download station data"
                log.error(self.lastKnownError)
                return False
            stationData = d.read()
            observations = json.loads(stationData)
            # self.parseStationDataWithKey(observations)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get station data"
            log.error(self.lastKnownError)
            return

    def getForecastWithKey(self, apiKey):
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        forecastURL = self.apiForecastURL + '?geocode=' + str(llat) + ',' + str(llon) \
                      + '&language=en-US&units=m&format=json&apiKey=' + str(apiKey)
        try:
            d = self.openURL(forecastURL)
            if d is None:
                self.lastKnownError = "Cannot get forecast data"
                log.error(self.lastKnownError)
                return False
            forecastData = d.read()
            forecast = json.loads(forecastData)
            self.parseForecastWithKey(forecast)
            return True
        except Exception, e:
            self.lastKnownError = "Error: Cannot get forecast data"
            log.error(self.lastKnownError)
            return False

    def parseForecastWithKey(self, forecast):
        forecastDayPart = forecast.get('daypart', None)[0]
        arrIconCodeDP = forecastDayPart['iconCode'] # should get only odd icons/conditions for day part
        arrRelativeHumidityDP = forecastDayPart['relativeHumidity'] #interpolate max and min
        arrWindSpeddDP = forecastDayPart['windSpeed']

        arrTS = forecast['validTimeUtc']
        arrTemperatureMin = forecast['temperatureMin']
        arrTemperatureMax = forecast['temperatureMax']
        arrQPF = forecast['qpf']

        for index, timeStamp in enumerate(arrTS):
            mintemp = self.__toFloat(arrTemperatureMin[index])
            maxtemp = self.__toFloat(arrTemperatureMax[index])
            minrh = self.__toFloat(arrRelativeHumidityDP[2*index])
            maxrh = self.__toFloat(arrRelativeHumidityDP[2*index+1])
            windDay = arrWindSpeddDP[2*index]
            windNight = arrWindSpeddDP[2*index+1]
            wind = None
            if windDay is not None and windNight is not  None:
                wind = (self.__toFloat(windDay) + self.__toFloat(windNight)) / 2.
                wind = wind / 3.6  # converted from kmetersph to mps
            qpf = arrQPF[index]
            condition = self.conditionConvertWithKey(arrIconCodeDP[2 * index])

            if mintemp is not None:
                self.addValue(RMParser.dataType.MINTEMP, timeStamp, mintemp, False)
            if maxtemp is not None:
                self.addValue(RMParser.dataType.MAXTEMP, timeStamp, maxtemp, False)
            if minrh is not None:
                self.addValue(RMParser.dataType.MINRH, timeStamp, minrh, False)
            if maxrh is not None:
                self.addValue(RMParser.dataType.MAXRH, timeStamp, maxrh, False)
            if wind is not None:
                self.addValue(RMParser.dataType.WIND, timeStamp, wind, False)
            if qpf is not None:
                self.addValue(RMParser.dataType.QPF, timeStamp, qpf, False)
            if condition is not None:
                self.addValue(RMParser.dataType.CONDITION, timeStamp, condition, False)

    def conditionConvertWithKey(self, iconIndex):
        if iconIndex is None:
            return  None
        if iconIndex < 3:
            return RMParser.conditionType.FunnelCloud
        elif iconIndex < 5 or iconIndex == 38:
            return RMParser.conditionType.Thunderstorm
        elif iconIndex in (5, 7, 17, 18):
            return RMParser.conditionType.RainSnow
        elif iconIndex == 6:
            return RMParser.conditionType.RainIce
        elif iconIndex in (8, 10):
            return RMParser.conditionType.FreezingRain
        elif iconIndex in (9, 11, 35):
            return RMParser.conditionType.LightRain
        elif iconIndex in (12, 40):
            return RMParser.conditionType.HeavyRain
        elif iconIndex in (13, 14, 15, 16, 41, 42, 43, 46):
            return RMParser.conditionType.Snow
        elif iconIndex == 20:
            return RMParser.conditionType.Fog
        elif iconIndex == 21:
            return RMParser.conditionType.Haze
        elif iconIndex == 22:
            return RMParser.conditionType.Smoke
        elif iconIndex in (23, 24):
            return RMParser.conditionType.Windy
        elif iconIndex == 25:
            return RMParser.conditionType.IcePellets
        elif iconIndex == 26:
            return RMParser.conditionType.FewClouds
        elif iconIndex in (27, 28):
            return RMParser.conditionType.MostlyCloudy
        elif iconIndex in (29, 30):
            return RMParser.conditionType.PartlyCloudy
        elif iconIndex in (31, 32, 33, 34, 36):
            return RMParser.conditionType.Fair
        elif iconIndex in (37, 47):
            return RMParser.conditionType.ThunderstormInVicinity
        elif iconIndex in (39, 45):
            return RMParser.conditionType.RainShowers
        else:
            return RMParser.conditionType.Unknown

# NO API KEY
    def getStationDataNoKey(self, stationName):
        try:
            timeNow = rmNowDateTime()
            timeYesterday = rmNowDateTime().fromordinal(timeNow.toordinal() - 1)
            yyyyy = timeYesterday.year
            mmy = timeYesterday.month
            ddy = timeYesterday.day

            dataURL = "https://www.wunderground.com/weatherstation/WXDailyHistory.asp?ID=" + stationName + "&day=" + str(
                ddy) + "&month=" + str(mmy) + "&year=" + str(
                yyyyy) + "&graphspan=week&format=0&units=metric"

            d = self.openURL(dataURL, headers=self.headers)
            if d is None:
                log.error("Cannot download station %s data" % stationName)
                self.lastKnownError = "Error: Failed to get custom station"
                return False

            data = d.read()
            data = data.replace("\n<br>", "")
            data = data.replace("<br>", "")
            data = data[1:]
            arrLines = data.splitlines()

            valuesLine = None
            headerLine = arrLines[0]

            # first line is the header
            dateString = str(yyyyy) + '-' + str(mmy) + '-' + str(ddy)

            for line in arrLines:
                if line.startswith(dateString):
                    valuesLine = line
                    break
            headers = headerLine.split(',')
            values = valuesLine.split(',')
            dictValues = dict(zip(headers, values))

            self.parseStationYesterdayDataNoKey(dictValues)
            return True
        except:
            return False

    def getNearbyStationsNoKey(self):
        MIN_STATIONS = 1
        MAX_STATIONS = 20
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        stationsURL = "https://stationdata.wunderground.com/cgi-bin/stationdata?v=2.0&type=ICAO%2CPWS&units=metric&format=json&maxage=1800&maxstations=" \
                      + str(MAX_STATIONS) + "&minstations=" + str(MIN_STATIONS) + "&centerLat=" + str(llat) + "&centerLon=" \
                      + str(llon) + "&height=400&width=400&iconsize=2&callback=__ng_jsonp__.__req1.finished"
        try:
            # WARNING: WE PROBABLY SHOULD FAIL IF WE CAN'T GET STATIONS IF USER KNOWS STATION_ID
            log.debug("Downloading station data from: %s" % stationsURL)
            d = self.openURL(stationsURL, headers=self.headers)
            if d is None:
                self.lastKnownError = "Cannot download nearby stations"
                log.error(self.lastKnownError)
            # extract object from callback parameter
            stationsData = d.read()
            stationsObj = stationsData[stationsData.find("{"):stationsData.rfind("}") + 1]
            # log.info(stationsObj)
            stations = json.loads(stationsObj)
            self.parseNearbyStationsNoKey(stations)
        except Exception, e:
            self.lastKnownError = "ERROR: Cannot get nearby stations"
            log.error(self.lastKnownError)
            return

    def parseNearbyStationsNoKey(self, jsonData):
        stations = jsonData["stations"]
        s = self.settings
        llat = s.location.latitude
        llon = s.location.longitude
        arrStations = []
        for stationDict in stations:
            stationId = stationDict["id"]
            stationType = stationDict["type"]
            if stationType == "PWS":
                lat1 = stationDict["latitude"]
                lon1 = stationDict["longitude"]
                distance = distanceBetweenGeographicCoordinatesAsKm(lat1, lon1, llat, llon)
                arrStations.append({'id':stationId, 'lat':lat1, 'lon':lon1, 'distance':distance})

        arrStations = sorted(arrStations, key=lambda k: k['distance'])
        for stationDict in arrStations:
            self.params["_nearbyStationsIDList"].append(stationDict['id'] +  " (" + str(round(stationDict['distance'],1)) + "km" + "; lat=" +
                                                str(round(stationDict['lat'], 2)) + ", lon=" + str(round(stationDict['lon'], 2)) + ")")

    def parseStationYesterdayDataNoKey(self, data):
        #daily summary for yesterday
        try:
            l = RMWeatherDataLimits()

            temperature = self.__toFloat(data["TemperatureAvgC"])
            mintemp = self.__toFloat(data["TemperatureLowC"])
            maxtemp = self.__toFloat(data["TemperatureHighC"])
            rh = self.__toFloat(data["HumidityAvg"])
            minrh = self.__toFloat(data["HumidityLow"])
            maxrh = self.__toFloat(data["HumidityHigh"])
            dewpoint = self.__toFloat(data["DewpointAvgC"])
            wind = self.__toFloat(data["WindSpeedAvgKMH"])
            maxpressure = self.__toFloat(data["PressureMaxhPa"])
            minpressure = self.__toFloat(data["PressureMinhPa"])
            rain = self.__toFloat(data["PrecipitationSumCM"]) * 10.0  # from cm to mm

            if wind is not None:
                wind = wind / 3.6  # converted from kmetersph to mps

            if maxpressure is not None:
                maxpressure = l.sanitize(RMWeatherDataType.PRESSURE, maxpressure / 10.0) # converted to from hpa to kpa

            if minpressure is not None:
                minpressure = l.sanitize(RMWeatherDataType.PRESSURE, minpressure / 10.0)

            pressure = None
            if maxpressure is not None and minpressure is not None:
                pressure = (maxpressure + minpressure) / 2.0

            #log.info("rh:%s minrh: %s maxrh: %s pressure: %s temp: %s mintemp: %s maxtemp: %s" % (rh, minrh, maxrh, pressure, temperature, mintemp, maxtemp))

            timestamp = rmCurrentDayTimestamp()
            timestamp = rmGetStartOfDay(timestamp - 12*3600)

            self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temperature, False)
            self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp, False)
            self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp, False)
            self.addValue(RMParser.dataType.RH, timestamp, rh, False)
            self.addValue(RMParser.dataType.MINRH, timestamp, minrh, False)
            self.addValue(RMParser.dataType.MAXRH, timestamp, maxrh, False)
            self.addValue(RMParser.dataType.WIND, timestamp, wind, False)
            self.addValue(RMParser.dataType.RAIN, timestamp, rain, False)
            self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint, False)
            self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure, False)

        except Exception, e:
            self.lastKnownError = "ERROR: Failed to get historical data"
            log.error("%s: %s" % (self.lastKnownError, e))

    def __parseDateTime(self, timestamp, roundToHour = True):
        if timestamp is None:
            return None
        if roundToHour:
            return timestamp - (timestamp % 3600)
        else:
            return timestamp

    def __toFloat(self, value):
        try:
            if value is None:
                return value
            return float(value)
        except:
            return None

    def __toInt(self, value):
        try:
            if value is None:
                return value
            return int(value)
        except:
            return None

