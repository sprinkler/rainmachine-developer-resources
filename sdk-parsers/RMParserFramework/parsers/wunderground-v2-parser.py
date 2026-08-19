# Copyright (c) 2024 RainMachine, Green Electronics LLC
# All rights reserved.

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmGetStartOfDay, rmCurrentDayTimestamp, rmDeltaDayFromTimestamp
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
                log.warning("WUndergroundV2: libssl unavailable: %s" % e)
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


class WUndergroundV2(RMParser):
    parserName        = "WUnderground V2 Parser"
    parserDescription = "Global weather service from https://preview.wunderground.com/"
    parserForecast    = True
    parserHistorical  = True
    parserEnabled     = False
    parserDebug       = False
    parserID          = "wundergroundv2"
    parserInterval    = 1 * 3600

    params = {
        "apiKey":                None,
        "stationId":             None,
        "_nearbyStationsIDList": [],
    }

    apiLocationURL   = "https://api.weather.com/v3/location/near"
    apiHistoricalURL = "https://api.weather.com/v2/pws/dailysummary/7day"
    apiForecastURL   = "https://api.weather.com/v3/wx/forecast/daily/5day"

    def isEnabledForLocation(self, timezone, lat, long):
        apiKey    = self.params.get("apiKey")
        stationId = self.params.get("stationId")
        return (WUndergroundV2.parserEnabled
                and isinstance(apiKey, str) and len(apiKey) > 0
                and isinstance(stationId, str) and len(stationId) > 0)

    #-----------------------------------------------------------------------
    # Transport
    #
    # openURL() is overridden so the request code above needs no changes: it
    # still gets back an object with .read(). Controllers whose ssl module can
    # send SNI keep using urllib2 and only fall back to ctypes if it fails;
    # controllers without SNI go straight to the ctypes path, which is the
    # only thing that reaches api.weather.com on that firmware.

    agent = "RainMachine-WUndergroundV2/1.0"
    timeout = 60

    _answered = False
    _sniChecked = False
    _sniAvailable = False

    def hasNativeSNI(self):
        if not WUndergroundV2._sniChecked:
            WUndergroundV2._sniAvailable = (bool(getattr(ssl, "HAS_SNI", False))
                                            and hasattr(ssl, "SSLContext"))
            WUndergroundV2._sniChecked = True
        return WUndergroundV2._sniAvailable

    def __viaUrllib(self, url):
        request = urllib2.Request(url, headers={"User-Agent": self.agent,
                                                "Accept": "application/json"})
        try:
            response = urllib2.urlopen(request, timeout=self.timeout)
            return SNIResponse(response.read(), response.getcode())
        except urllib2.HTTPError, e:
            log.warning("WUndergroundV2: HTTP %s from %s" % (e.code, self.__safeURL(url)))
        except Exception, e:
            log.warning("WUndergroundV2: urllib2 failed: %s" % e)
        return None

    def __viaCtypes(self, url):
        # Embedded hardware drops the occasional handshake or read; one retry
        # turns an intermittent failure into a successful refresh.
        for attempt in (1, 2):
            try:
                status, body = sniGet(url, self.timeout, self.agent)
            except Exception, e:
                if attempt == 1:
                    time.sleep(1)
                    continue
                log.warning("WUndergroundV2: libssl transport failed: %s" % e)
                return None
            if status != 200:
                # A status code means the CDN and the API answered, so the
                # SNI handshake worked and this result is definitive.
                # Falling back to urllib2 would only produce a misleading
                # 421 from a stack that cannot send SNI in the first place.
                log.warning("WUndergroundV2: HTTP %s from %s" % (status, self.__safeURL(url)))
                self._answered = True
                return None
            return SNIResponse(body, status)
        return None

    def __safeURL(self, url):
        at = url.find("apiKey=")
        return url if at < 0 else url[:at] + "apiKey=***"

    def openURL(self, url, params=None, encodeParameters=True, headers={}):
        if params:
            query = urllib.urlencode(params) if encodeParameters else params
            url = "?".join([url, query])

        binding = SSLBinding.get()
        log.debug("WUndergroundV2: python=%s sni=%s libssl=%s url=%s"
                  % (sys.version.split()[0],
                     "yes" if self.hasNativeSNI() else "no",
                     binding.path if binding else "none",
                     self.__safeURL(url)))

        self._answered = False
        order = ([self.__viaUrllib, self.__viaCtypes] if self.hasNativeSNI()
                 else [self.__viaCtypes, self.__viaUrllib])
        for transport in order:
            try:
                response = transport(url)
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
            self.lastKnownError = "Error: request failed on every available transport"
        log.error(self.lastKnownError)
        return None

    def perform(self):
        self.params["_nearbyStationsIDList"] = []
        self.lastKnownError = ""

        apiKey    = self.params.get("apiKey")
        stationId = self.params.get("stationId")

        if not isinstance(apiKey, str) or not apiKey:
            self.lastKnownError = "Error: No API Key provided."
            log.error(self.lastKnownError)
            return

        if not isinstance(stationId, str) or not stationId:
            self.lastKnownError = "Error: No Station ID provided."
            log.error(self.lastKnownError)
            return

        self.__getNearbyStations(apiKey)

        hasHistorical = self.__getHistorical(apiKey, stationId)
        hasForecast   = self.__getForecast(apiKey)

        if not hasHistorical and not hasForecast:
            self.lastKnownError = "Error: No data received."
            log.error(self.lastKnownError)
        elif not hasHistorical:
            log.warning("WUndergroundV2: no historical data.")
        elif not hasForecast:
            log.warning("WUndergroundV2: no forecast data.")
        else:
            log.info("WUndergroundV2: historical and forecast data retrieved.")

    def __getNearbyStations(self, apiKey):
        s = self.settings
        URLParams = [
            ("geocode", "%s,%s" % (s.location.latitude, s.location.longitude)),
            ("product", "pws"),
            ("format",  "json"),
            ("apiKey",  str(apiKey)),
        ]
        try:
            d = self.openURL(self.apiLocationURL, URLParams)
            if d is None:
                log.warning("WUndergroundV2: cannot fetch nearby stations.")
                return
            data = json.loads(d.read())
            self.__parseNearbyStations(data)
        except Exception, e:
            log.warning("WUndergroundV2: nearby station lookup failed: %s" % e)

    def __parseNearbyStations(self, data):
        try:
            location   = data["location"]
            stationIds = location.get("stationId", []) or []
            latitudes  = location.get("latitude",  []) or []
            longitudes = location.get("longitude", []) or []
            distances  = location.get("distanceKm", []) or []

            stations = []
            for i, sid in enumerate(stationIds):
                if sid is None:
                    continue
                stations.append({
                    "id":       sid,
                    "lat":      latitudes[i],
                    "lon":      longitudes[i],
                    "distance": distances[i],
                })
            stations.sort(key=lambda x: x["distance"])

            for st in stations:
                self.params["_nearbyStationsIDList"].append(
                    "%s (%.1fkm; lat=%.2f, lon=%.2f)" % (
                        st["id"], st["distance"], st["lat"], st["lon"]))
        except Exception, e:
            log.warning("WUndergroundV2: error parsing nearby stations: %s" % e)

    def __getHistorical(self, apiKey, stationId):
        URLParams = [
            ("stationId", str(stationId)),
            ("format",    "json"),
            ("units",     "m"),
            ("apiKey",    str(apiKey)),
        ]
        try:
            d = self.openURL(self.apiHistoricalURL, URLParams)
            if d is None:
                self.lastKnownError = "Error: Cannot download historical data."
                log.error(self.lastKnownError)
                return False
            data = json.loads(d.read())

            if self.parserDebug:
                with open("wu2-historical-dump.json", "w") as f:
                    json.dump(data, f, indent=2)

            return self.__parseHistorical(data)
        except Exception, e:
            self.lastKnownError = "Error: Cannot get historical data."
            log.error(self.lastKnownError)
            log.exception(e)
            return False

    def __parseHistorical(self, data):
        tsToday     = rmCurrentDayTimestamp()
        tsYesterday = rmDeltaDayFromTimestamp(tsToday, -1)
        limits      = RMWeatherDataLimits()
        hasData     = False

        try:
            for obs in data.get("summaries", []):
                epoch = obs.get("epoch")
                if epoch is None:
                    continue
                tsDay = rmGetStartOfDay(epoch)

                m = obs.get("metric") or {}

                temperature = self.__toFloat(m.get("tempAvg"))
                mintemp     = self.__toFloat(m.get("tempLow"))
                maxtemp     = self.__toFloat(m.get("tempHigh"))
                rh          = self.__toFloat(obs.get("humidityAvg"))
                minrh       = self.__toFloat(obs.get("humidityLow"))
                maxrh       = self.__toFloat(obs.get("humidityHigh"))
                dewpoint    = self.__toFloat(m.get("dewptAvg"))
                wind        = self.__toFloat(m.get("windspeedAvg"))
                rain        = self.__toFloat(m.get("precipTotal"))

                if wind is not None:
                    wind = wind / 3.6  # km/h -> m/s

                maxpressure = self.__toFloat(m.get("pressureMax"))
                minpressure = self.__toFloat(m.get("pressureMin"))
                if maxpressure is not None:
                    maxpressure = limits.sanitize(RMWeatherDataType.PRESSURE, maxpressure / 10.0)
                if minpressure is not None:
                    minpressure = limits.sanitize(RMWeatherDataType.PRESSURE, minpressure / 10.0)
                pressure = None
                if maxpressure is not None and minpressure is not None:
                    pressure = (maxpressure + minpressure) / 2.0

                if tsDay == tsYesterday:
                    solarRaw = self.__toFloat(m.get("solarRadiationHigh"))
                    solar    = solarRaw * 0.0864 if solarRaw is not None else None  # W/m^2 -> MJ/m^2/day (peak reading used as daily proxy)

                    self.addValue(RMParser.dataType.TEMPERATURE,    tsDay, temperature, False)
                    self.addValue(RMParser.dataType.MINTEMP,        tsDay, mintemp,     False)
                    self.addValue(RMParser.dataType.MAXTEMP,        tsDay, maxtemp,     False)
                    self.addValue(RMParser.dataType.RH,             tsDay, rh,          False)
                    self.addValue(RMParser.dataType.MINRH,          tsDay, minrh,       False)
                    self.addValue(RMParser.dataType.MAXRH,          tsDay, maxrh,       False)
                    self.addValue(RMParser.dataType.WIND,           tsDay, wind,        False)
                    self.addValue(RMParser.dataType.RAIN,           tsDay, rain,        False)
                    self.addValue(RMParser.dataType.DEWPOINT,       tsDay, dewpoint,    False)
                    self.addValue(RMParser.dataType.PRESSURE,       tsDay, pressure,    False)
                    self.addValue(RMParser.dataType.SOLARRADIATION, tsDay, solar,       False)
                    hasData = True
                elif tsDay == tsToday:
                    # Today's RAIN only - avoids overwriting forecast data
                    self.addValue(RMParser.dataType.RAIN, tsDay, rain, False)
                    hasData = True

            return hasData
        except Exception, e:
            self.lastKnownError = "Warning: Failed to parse historical data."
            log.error(self.lastKnownError)
            log.exception(e)
            return False

    def __getForecast(self, apiKey):
        s = self.settings
        URLParams = [
            ("geocode",  "%s,%s" % (s.location.latitude, s.location.longitude)),
            ("language", "en-US"),
            ("units",    "m"),
            ("format",   "json"),
            ("apiKey",   str(apiKey)),
        ]
        try:
            d = self.openURL(self.apiForecastURL, URLParams)
            if d is None:
                self.lastKnownError = "Error: Cannot download forecast data."
                log.error(self.lastKnownError)
                return False
            data = json.loads(d.read())

            if self.parserDebug:
                with open("wu2-forecast-dump.json", "w") as f:
                    json.dump(data, f, indent=2)

            self.__parseForecast(data)
            return True
        except Exception, e:
            self.lastKnownError = "Error: Cannot get forecast data."
            log.error(self.lastKnownError)
            log.exception(e)
            return False

    def __parseForecast(self, data):
        daypartList = data.get("daypart") or []
        if not daypartList:
            log.warning("WUndergroundV2: no daypart data in forecast response.")
            return
        dp = daypartList[0]

        arrIconCode     = dp.get("iconCode")             or []
        arrRH           = dp.get("relativeHumidity")     or []
        arrWind         = dp.get("windSpeed")            or []
        arrDewpoint     = dp.get("temperatureDewPoint")  or []
        arrPrecipChance = dp.get("precipChance")         or []
        arrCloudCover   = dp.get("cloudCover")           or []

        arrTS      = data.get("validTimeUtc")   or []
        arrMinTemp = data.get("temperatureMin") or []
        arrMaxTemp = data.get("temperatureMax") or []
        arrQPF     = data.get("qpf")            or []

        for i, ts in enumerate(arrTS):
            mintemp = self.__toFloat(arrMinTemp[i] if i < len(arrMinTemp) else None)
            maxtemp = self.__toFloat(arrMaxTemp[i] if i < len(arrMaxTemp) else None)
            qpf     = self.__toFloat(arrQPF[i]     if i < len(arrQPF)     else None)

            ni = 2 * i      # night part index
            di = 2 * i + 1  # day part index

            minrh = self.__toFloat(arrRH[ni] if ni < len(arrRH) else None)
            maxrh = self.__toFloat(arrRH[di] if di < len(arrRH) else None)

            windNight = self.__toFloat(arrWind[ni] if ni < len(arrWind) else None)
            windDay   = self.__toFloat(arrWind[di] if di < len(arrWind) else None)
            wind = None
            if windNight is not None and windDay is not None:
                wind = (windNight + windDay) / 2.0 / 3.6  # km/h -> m/s
            elif windDay is not None:
                wind = windDay / 3.6
            elif windNight is not None:
                wind = windNight / 3.6

            dewNight = self.__toFloat(arrDewpoint[ni] if ni < len(arrDewpoint) else None)
            dewDay   = self.__toFloat(arrDewpoint[di] if di < len(arrDewpoint) else None)
            dewpoint = None
            if dewNight is not None and dewDay is not None:
                dewpoint = (dewNight + dewDay) / 2.0
            elif dewDay is not None:
                dewpoint = dewDay
            elif dewNight is not None:
                dewpoint = dewNight

            popNight = self.__toFloat(arrPrecipChance[ni] if ni < len(arrPrecipChance) else None)
            popDay   = self.__toFloat(arrPrecipChance[di] if di < len(arrPrecipChance) else None)
            pop = None
            if popNight is not None and popDay is not None:
                pop = max(popNight, popDay)
            elif popDay is not None:
                pop = popDay
            elif popNight is not None:
                pop = popNight

            skyNight = self.__toFloat(arrCloudCover[ni] if ni < len(arrCloudCover) else None)
            skyDay   = self.__toFloat(arrCloudCover[di] if di < len(arrCloudCover) else None)
            skycover = None
            if skyNight is not None and skyDay is not None:
                skycover = (skyNight + skyDay) / 2.0
            elif skyDay is not None:
                skycover = skyDay
            elif skyNight is not None:
                skycover = skyNight

            # RainMachine's SKYCOVER is a 0..1 fraction (rmLimits caps it at 1)
            # but cloudCover is reported as a percentage, so every value was
            # being rejected: "SKYCOVER value 25.5 more than limits maximum of
            # 1, invalidated".
            if skycover is not None:
                skycover = skycover / 100.0

            iconCode  = arrIconCode[ni] if ni < len(arrIconCode) else None
            condition = self.__conditionConvert(iconCode)

            if mintemp   is not None: self.addValue(RMParser.dataType.MINTEMP,   ts, mintemp,   False)
            if maxtemp   is not None: self.addValue(RMParser.dataType.MAXTEMP,   ts, maxtemp,   False)
            if minrh     is not None: self.addValue(RMParser.dataType.MINRH,     ts, minrh,     False)
            if maxrh     is not None: self.addValue(RMParser.dataType.MAXRH,     ts, maxrh,     False)
            if wind      is not None: self.addValue(RMParser.dataType.WIND,      ts, wind,      False)
            if qpf       is not None: self.addValue(RMParser.dataType.QPF,       ts, qpf,       False)
            if condition is not None: self.addValue(RMParser.dataType.CONDITION, ts, condition, False)
            if dewpoint  is not None: self.addValue(RMParser.dataType.DEWPOINT,  ts, dewpoint,  False)
            if pop       is not None: self.addValue(RMParser.dataType.POP,       ts, pop,       False)
            if skycover  is not None: self.addValue(RMParser.dataType.SKYCOVER,  ts, skycover,  False)

    def __conditionConvert(self, iconCode):
        if iconCode is None:
            return None
        if iconCode < 3:
            return RMParser.conditionType.FunnelCloud
        elif iconCode < 5 or iconCode == 38:
            return RMParser.conditionType.Thunderstorm
        elif iconCode in (5, 7, 17, 18):
            return RMParser.conditionType.RainSnow
        elif iconCode == 6:
            return RMParser.conditionType.RainIce
        elif iconCode in (8, 10):
            return RMParser.conditionType.FreezingRain
        elif iconCode in (9, 11, 35):
            return RMParser.conditionType.LightRain
        elif iconCode in (12, 40):
            return RMParser.conditionType.HeavyRain
        elif iconCode in (13, 14, 15, 16, 41, 42, 43, 46):
            return RMParser.conditionType.Snow
        elif iconCode == 20:
            return RMParser.conditionType.Fog
        elif iconCode == 21:
            return RMParser.conditionType.Haze
        elif iconCode == 22:
            return RMParser.conditionType.Smoke
        elif iconCode in (23, 24):
            return RMParser.conditionType.Windy
        elif iconCode == 25:
            return RMParser.conditionType.IcePellets
        elif iconCode == 26:
            return RMParser.conditionType.FewClouds
        elif iconCode in (27, 28):
            return RMParser.conditionType.MostlyCloudy
        elif iconCode in (29, 30):
            return RMParser.conditionType.PartlyCloudy
        elif iconCode in (31, 32, 33, 34, 36):
            return RMParser.conditionType.Fair
        elif iconCode in (37, 47):
            return RMParser.conditionType.ThunderstormInVicinity
        elif iconCode in (39, 45):
            return RMParser.conditionType.RainShowers
        else:
            return RMParser.conditionType.Unknown

    def __toFloat(self, value):
        try:
            if value is None:
                return None
            return float(value)
        except:
            return None


if __name__ == "__main__":
    import os

    class _Location(object):
        latitude  = float(os.environ.get("RM_LAT",       "44.43"))
        longitude = float(os.environ.get("RM_LON",       "26.10"))
        elevation = float(os.environ.get("RM_ELEVATION",  "80.0"))

    class _Settings(object):
        location = _Location()

    p = WUndergroundV2()
    p.parserDebug = True
    p.settings = _Settings()
    p.params["apiKey"]    = os.environ.get("WU_API_KEY",    "")
    p.params["stationId"] = os.environ.get("WU_STATION_ID", "")
    p.perform()

    print "\n--- WU V2 result: %d entries ---" % len(p.result)
    for ts in sorted(p.result):
        print p.result[ts]
    if p.params.get("_nearbyStationsIDList"):
        print "\nNearby stations:"
        for st in p.params["_nearbyStationsIDList"]:
            print "  " + st
