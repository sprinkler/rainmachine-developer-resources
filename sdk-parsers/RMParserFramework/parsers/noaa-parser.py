# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmTimeUtils import *
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType

import ctypes
import datetime
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
        self.lastKnownError = ""

        # Resolve the NWS grid point once; every other endpoint is derived from
        # this one. api.weather.gov is the modern NWS API - no RainMachine
        # proxy, no hardcoded token, no legacy NDFD XML.
        pointsURL = "https://api.weather.gov/points/%s,%s" % (
            s.location.latitude, s.location.longitude)

        d = self.openURL(pointsURL)
        if d is None:
            self.lastKnownError = "Error: Cannot resolve NWS grid point"
            log.error(self.lastKnownError)
            return
        try:
            points = json.loads(d.read())
            props = points.get("properties", {})
            hourlyURL = props.get("forecastHourly")
            dailyURL  = props.get("forecast")
            gridURL   = props.get("forecastGridData")
        except Exception, e:
            self.lastKnownError = "Error: Cannot parse NWS grid point response"
            log.error(self.lastKnownError)
            log.exception(e)
            return

        if not (hourlyURL and gridURL):
            self.lastKnownError = "Error: NWS grid point response is incomplete"
            log.error(self.lastKnownError)
            return

        hasHourly = self.getHourlyData(hourlyURL, gridURL)
        hasDaily  = self.getDailyData(dailyURL) if dailyURL else False

        # If we didn't get Hourly data we consider a fail and retry the whole
        # parser operation. We remove any values obtained by the daily call so
        # we can trigger parser retry.
        if not hasHourly:
            self.clearValues()

        if self.parserDebug:
            log.debug(self.result)

    #-----------------------------------------------------------------------------------------------
    #
    # Get hourly data from the NWS hourly forecast and the grid data.
    #
    def getHourlyData(self, hourlyURL, gridURL):
        d = self.openURL(hourlyURL)
        if d is None:
            log.warning("NOAA: cannot fetch hourly forecast.")
            return False
        try:
            data = json.loads(d.read())
            periods = data.get("properties", {}).get("periods", [])
        except Exception, e:
            log.warning("NOAA: cannot parse hourly forecast: %s" % e)
            return False

        grid = self.__fetchGridData(gridURL)
        skyByHour = self.__gridSeries(grid, "skyCover", byHour=True)
        qpfByHour = self.__gridSeries(grid, "quantitativePrecipitation", byHour=False)

        todayTimestamp = rmCurrentDayTimestamp()
        maxDayTimestamp = todayTimestamp + globalSettings.parserDataSizeInDays * 86400

        maxDayRH = {}
        minDayRH = {}

        for p in periods:
            ts = rmTimestampFromDateAsStringWithOffset(p.get("startTime"))
            if ts is None or ts >= maxDayTimestamp:
                continue

            temp = self.__toFloat(p.get("temperature"))
            if temp is not None and p.get("temperatureUnit") == "F":
                temp = (temp - 32) * 5.0 / 9.0

            dew = self.__value(p.get("dewpoint"))
            if dew is not None and str(p.get("dewpoint", {}).get("unitCode", "")).endswith("degF"):
                dew = (dew - 32) * 5.0 / 9.0

            rh   = self.__value(p.get("relativeHumidity"))
            pop  = self.__value(p.get("probabilityOfPrecipitation"))
            wind = self.__parseWind(p.get("windSpeed"))
            sky  = skyByHour.get(ts)

            if rh is not None:
                day = rmGetStartOfDay(ts)
                if day not in minDayRH or rh < minDayRH[day]:
                    minDayRH[day] = rh
                if day not in maxDayRH or rh > maxDayRH[day]:
                    maxDayRH[day] = rh

            if temp  is not None: self.addValue(RMParser.dataType.TEMPERATURE, ts, temp, False)
            if rh    is not None: self.addValue(RMParser.dataType.RH,          ts, rh,   False)
            if dew   is not None: self.addValue(RMParser.dataType.DEWPOINT,    ts, dew,  False)
            if wind  is not None: self.addValue(RMParser.dataType.WIND,        ts, wind, False)
            if pop   is not None: self.addValue(RMParser.dataType.POP,         ts, pop,  False)
            if sky   is not None: self.addValue(RMParser.dataType.SKYCOVER,    ts, sky / 100.0, False)

        # QPF: quantitativePrecipitation reports the amount for a multi-hour
        # interval (e.g. PT6H). Store the interval amount at its start time;
        # the framework sums QPF across the day.
        for ts, qpf in qpfByHour.items():
            if ts < maxDayTimestamp:
                self.addValue(RMParser.dataType.QPF, ts, qpf, False)

        for day, value in minDayRH.items():
            self.addValue(RMParser.dataType.MINRH, day, value, False)
        for day, value in maxDayRH.items():
            self.addValue(RMParser.dataType.MAXRH, day, value, False)

        if self.parserDebug:
            with open("noaa-hourly-%s.json" % rmTimestampToDateAsString(todayTimestamp), "w") as f:
                json.dump(data, f, indent=2)

        return True

    #-----------------------------------------------------------------------------------------------
    #
    # Get daily data from the NWS daily forecast (day/night periods).
    #
    def getDailyData(self, dailyURL):
        if not dailyURL:
            return False
        d = self.openURL(dailyURL)
        if d is None:
            log.warning("NOAA: cannot fetch daily forecast.")
            return False
        try:
            data = json.loads(d.read())
            periods = data.get("properties", {}).get("periods", [])
        except Exception, e:
            log.warning("NOAA: cannot parse daily forecast: %s" % e)
            return False

        todayTimestamp = rmCurrentDayTimestamp()
        maxDayTimestamp = todayTimestamp + globalSettings.parserDataSizeInDays * 86400

        for p in periods:
            ts = rmTimestampFromDateAsStringWithOffset(p.get("startTime"))
            if ts is None or ts >= maxDayTimestamp:
                continue

            temp = self.__toFloat(p.get("temperature"))
            if temp is not None and p.get("temperatureUnit") == "F":
                temp = (temp - 32) * 5.0 / 9.0

            if p.get("isDaytime"):
                self.addValue(RMParser.dataType.MAXTEMP, ts, temp, False)
            else:
                self.addValue(RMParser.dataType.MINTEMP, ts, temp, False)

            icon = p.get("icon") or ""
            slug = icon.split("?")[0].rsplit("/", 1)[-1].split(",", 1)[0]
            if slug:
                self.addValue(RMParser.dataType.CONDITION, ts, self.conditionConvert(slug), False)

        if self.parserDebug:
            with open("noaa-daily-%s.json" % rmTimestampToDateAsString(todayTimestamp), "w") as f:
                json.dump(data, f, indent=2)

        return True

    def __fetchGridData(self, gridURL):
        d = self.openURL(gridURL)
        if d is None:
            return None
        try:
            return json.loads(d.read()).get("properties", {})
        except Exception, e:
            log.warning("NOAA: cannot parse grid data: %s" % e)
            return None

    # Turns a gridData series into {timestamp: value}. byHour selects the
    # series that align to the hour (skyCover, relativeHumidity) over the ones
    # that report a multi-hour accumulation (quantitativePrecipitation).
    def __gridSeries(self, grid, key, byHour=True):
        result = {}
        if not grid:
            return result
        series = grid.get(key)
        if not series:
            return result
        for item in series.get("values", []) or []:
            validTime = item.get("validTime") or ""
            base = validTime.split("/")[0]
            ts = rmTimestampFromDateAsStringWithOffset(base)
            if ts is None:
                continue
            if byHour:
                ts = ts - (ts % 3600)
            if item.get("value") is not None:
                result[ts] = self.__toFloat(item["value"])
        return result

    def __value(self, field):
        if not isinstance(field, dict):
            return None
        return self.__toFloat(field.get("value"))

    def __parseWind(self, windSpeed):
        if not windSpeed:
            return None
        parts = windSpeed.split()
        try:
            val = float(parts[0])
        except (ValueError, TypeError):
            return None
        unit = parts[1].lower() if len(parts) > 1 else "mph"
        if unit.startswith("mph"):
            return val * 0.44704
        if unit.startswith("km"):
            return val / 3.6
        if unit.startswith("kt"):
            return val * 0.514444
        return None

    def __toFloat(self, value):
        try:
            if value is None:
                return None
            return float(value)
        except (ValueError, TypeError):
            return None


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
        elif 'sleet' in conditionStr:
            return  RMParser.conditionType.RainIce
        elif 'hail' in conditionStr:
            return  RMParser.conditionType.RainIce
        elif 'rasn' in conditionStr:
            return  RMParser.conditionType.RainSnow
        elif 'shra' in conditionStr:
            return  RMParser.conditionType.RainShowers
        elif 'tsra' in conditionStr:
            return  RMParser.conditionType.Thunderstorm
        elif 'sn' in conditionStr:
            return  RMParser.conditionType.Snow
        elif 'showers' in conditionStr:
            return  RMParser.conditionType.RainShowers
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
        elif 'haze' in conditionStr:
            return  RMParser.conditionType.Haze
        elif 'hot' in conditionStr:
            return  RMParser.conditionType.Hot
        elif 'cold' in conditionStr:
            return  RMParser.conditionType.Cold
        else:
            return  RMParser.conditionType.Unknown


if __name__ == "__main__":
    import os

    class _Location(object):
        latitude  = float(os.environ.get("RM_LAT",       "37.6"))
        longitude = float(os.environ.get("RM_LON",       "-121.8"))
        elevation = float(os.environ.get("RM_ELEVATION",  "80.0"))

    class _Settings(object):
        location = _Location()

    parser = NOAA()
    parser.parserDebug = True
    parser.settings = _Settings()
    parser.perform()

    print "\n--- NOAA result: %d entries ---" % len(parser.result)
    for ts in sorted(parser.result):
        print parser.result[ts]
    print "lastKnownError:", repr(parser.lastKnownError)