# WUnderground Backup - RainMachine weather service
# Weather Underground / The Weather Company v2 PWS observations + v3 forecast.
#
# Copyright (c) 2015-2024 RainMachine, Green Electronics LLC
#   Authors: Nicu Pavel <npavel@mini-box.com>, Ciprian Misaila
# Licensed under the GNU General Public License v3.0, as is the original.
#
# api.weather.com sits behind a CDN that requires TLS SNI. Python 2.7.3/2.7.8 on
# older firmware (Mini-8, Touch HD 2nd gen) cannot send SNI (PEP 466 landed in
# 2.7.9), so every request fails HTTP 421 before reaching the API - and those
# devices have no curl, no openssl binary and a BusyBox wget without TLS.
# libssl.so IS present and OpenSSL has done SNI since 0.9.8f, so this parser
# drives libssl through ctypes and calls SSL_set_tlsext_host_name()
# (= SSL_ctrl(ssl, 55, 0, host)) before the handshake, exactly as curl does.
# Verified on Mini-8 (2.7.3 / OpenSSL 1.0.1f) and Touch HD-16 (2.7.8 / 1.0.1e).
# The ctypes path does not verify certificates; neither did 2.7.3's urllib2.
# Devices with a modern Python keep using urllib2 and are unaffected.
#
# Leave stationId empty and the nearest working PWS is picked and verified
# automatically. Set stationId (uppercase, e.g. KCAPLEAS247) to override.
# API key: https://www.wunderground.com/member/api-keys (needs a registered PWS)
#
# UPGRADING - IMPORTANT: RainMachine looks a parser up in its database by
# parserName, and on a match whose fileName is unchanged it keeps the stored
# params wholesale - added params never appear, removed ones never go away.
# Whenever this parser's parameter list changes, SHIP IT UNDER A NEW FILE NAME
# (parserName and parserID may stay the same; the file name is what matters).
# Never reuse the name of a stock parser: "WUnderground Parser" already owns a
# database row, and colliding with it leaves the settings screen empty.

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmGetStartOfDay, rmCurrentDayTimestamp, rmDeltaDayFromTimestamp
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType

import ctypes, json, os, socket, ssl, struct, sys, time, urllib, urllib2

SNI_CTRL = 55           # SSL_CTRL_SET_TLSEXT_HOSTNAME
WANT = (2, 3, 5)        # WANT_READ / WANT_WRITE / SYSCALL

_LIBS = ["/usr/lib/libssl.so.1.0.0", "/lib/libssl.so.1.0.0", "/usr/lib/libssl.so.1.0.2",
         "/usr/lib/libssl.so.1.1", "/usr/lib/libssl.so", "/system/lib/libssl.so",
         "/system/lib64/libssl.so", "libssl.so.1.0.0", "libssl.so"]

ERR = {
    "001": "No API key - get one at wunderground.com/member/api-keys",
    "002": "No nearby stations returned for this location",
    "003": "No nearby station returned observations - set a station manually",
    "004": "Station returned no usable daily summaries",
    "100": "No SNI-capable transport on this device - cannot reach api.weather.com",
    "103": "Request failed on every available transport",
    "104": "Invalid or truncated JSON from api.weather.com",
    "105": "Cannot parse station data",
    "106": "Cannot parse forecast data",
    204: "Station has no data - wrong ID or it stopped uploading (the API key IS valid)",
    400: "Bad request - check the Station ID",
    401: "API key rejected - regenerate it at wunderground.com/member/api-keys",
    403: "API key not authorized - a PWS must be registered and uploading",
    404: "Station or endpoint not found - check the Station ID",
    421: "Misdirected Request - the CDN edge did not accept TLS SNI",
    429: "Rate limited by Weather Underground - too many requests",
}


def wuErr(code, extra=""):
    t = ERR.get(code, "Unexpected failure")
    if isinstance(code, int) and code >= 500:
        t = "Weather Underground server error"
    return "WU-%s: %s%s" % (code, t, (" (%s)" % extra) if extra else "")


class ApiError(Exception):
    # Definitive API failure - another transport will not help.
    def __init__(self, code, extra=""):
        Exception.__init__(self, wuErr(code, extra))
        self.code = code


class SNIError(Exception):
    pass


class _Ssl(object):
    # ctypes binding to the device's libssl, loaded once by absolute path:
    # ctypes.util.find_library() returns None on these images (no ldconfig).
    _inst = None
    _dead = False

    @classmethod
    def get(cls):
        if cls._dead:
            return None
        if cls._inst is None:
            try:
                cls._inst = _Ssl()
            except Exception, e:
                cls._dead = True
                log.warning("WU: libssl unavailable: %s" % e)
                return None
        return cls._inst

    def __init__(self):
        self.crypto, _ = self._dl([p.replace("libssl", "libcrypto") for p in _LIBS], 1)
        self.lib, self.path = self._dl(_LIBS, 0)
        s = self.lib
        vp, ci, cl, cc = ctypes.c_void_p, ctypes.c_int, ctypes.c_long, ctypes.c_char_p
        self.method = getattr(s, "SSLv23_client_method", None) or s.TLS_client_method
        self.method.restype = vp
        for n, a, r in (("SSL_CTX_new", [vp], vp), ("SSL_CTX_free", [vp], None),
                        ("SSL_new", [vp], vp), ("SSL_free", [vp], None),
                        ("SSL_set_fd", [vp, ci], ci), ("SSL_ctrl", [vp, ci, cl, cc], cl),
                        ("SSL_connect", [vp], ci), ("SSL_write", [vp, cc, ci], ci),
                        ("SSL_read", [vp, cc, ci], ci), ("SSL_shutdown", [vp], ci),
                        ("SSL_get_error", [vp, ci], ci)):
            f = getattr(s, n)
            f.argtypes = a
            if r:
                f.restype = r
        for n in ("SSL_library_init", "SSL_load_error_strings"):
            try:
                getattr(s, n)()
            except AttributeError:
                pass

    def _dl(self, names, glob):
        err = None
        for n in names:
            if n.startswith("/") and not os.path.exists(n):
                continue
            try:
                return (ctypes.CDLL(n, mode=ctypes.RTLD_GLOBAL) if glob else ctypes.CDLL(n)), n
            except Exception, e:
                err = e
        raise SNIError(str(err))


def _dechunk(body):
    out = []
    while body:
        nl = body.find("\r\n")
        if nl < 0:
            break
        try:
            size = int(body[:nl].split(";")[0].strip(), 16)
        except ValueError:
            break
        if size == 0:
            break
        out.append(body[nl + 2:nl + 2 + size])
        body = body[nl + 2 + size + 2:]
    return "".join(out)


def sniGet(url, timeout, agent):
    # HTTPS GET with SNI via libssl. Returns (status, body).
    b = _Ssl.get()
    if b is None:
        raise SNIError("libssl unavailable")
    rest = url.split("://", 1)[1]
    cut = rest.find("/")
    host = rest[:cut] if cut >= 0 else rest
    path = rest[cut:] if cut >= 0 else "/"

    sock = socket.create_connection((host, 443), timeout)
    # create_connection leaves the socket non-blocking, which makes OpenSSL's
    # blocking calls return WANT_READ. Restore blocking; time out in the kernel.
    sock.setblocking(1)
    try:
        tv = struct.pack("ll", int(timeout), 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, tv)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, tv)
    except Exception:
        pass

    s = b.lib
    ctx = con = None
    try:
        ctx = s.SSL_CTX_new(b.method())
        if not ctx:
            raise SNIError("SSL_CTX_new failed")
        con = s.SSL_new(ctx)
        if not con:
            raise SNIError("SSL_new failed")
        if s.SSL_set_fd(con, sock.fileno()) != 1:
            raise SNIError("SSL_set_fd failed")
        if s.SSL_ctrl(con, SNI_CTRL, 0, host) != 1:
            raise SNIError("cannot set SNI hostname")
        if s.SSL_connect(con) != 1:
            raise SNIError("handshake failed (err=%d)" % s.SSL_get_error(con, -1))

        # HTTP/1.1 - HTTP/1.0 draws 426 Upgrade Required from some edges.
        req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\n"
               "Accept: application/json\r\nConnection: close\r\n\r\n" % (path, host, agent))
        sent = 0
        while sent < len(req):
            n = s.SSL_write(con, req[sent:], len(req) - sent)
            if n <= 0:
                raise SNIError("SSL_write failed")
            sent += n

        # SSL_read <= 0 is not necessarily end of stream: on slow hardware it is
        # often WANT_READ, or SYSCALL from the SO_RCVTIMEO timer. Treating those
        # as EOF truncates the body and yields invalid JSON.
        parts = []
        buf = ctypes.create_string_buffer(16384)
        deadline = time.time() + timeout
        while True:
            n = s.SSL_read(con, buf, 16384)
            if n > 0:
                parts.append(buf.raw[:n])
                continue
            if s.SSL_get_error(con, n) in WANT and time.time() < deadline:
                time.sleep(0.1)
                continue
            break
        data = "".join(parts)
    finally:
        try:
            if con:
                s.SSL_shutdown(con)
                s.SSL_free(con)
            if ctx:
                s.SSL_CTX_free(ctx)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass

    i = data.find("HTTP/1.")
    if i < 0:
        raise SNIError("no HTTP response")
    data = data[i:]
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
        body = _dechunk(body)
    elif "content-length:" in head:
        # Catch a short read rather than handing truncated JSON upstream.
        try:
            want = int(head.split("content-length:")[1].split("\r\n")[0].strip())
            if len(body) < want:
                raise SNIError("truncated body (%d of %d bytes)" % (len(body), want))
        except (ValueError, IndexError):
            pass
    return status, body


class WUndergroundBackup(RMParser):
    parserName = "WUnderground Backup"
    parserDescription = ("Weather Underground PWS observations and forecast for controllers "
                         "whose Python cannot send TLS SNI (HTTP 421).")
    parserForecast = True
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserID = "wundergroundbackup"
    parserInterval = 1 * 3600

    # Plain dict on purpose: an OrderedDict here makes POST /parser/<id>/defaults
    # return HTTP 500 on device - the firmware rejects dict subclasses.
    params = {"_info": [],
              "apiKey": None,
              "stationId": None,
              "_nearbyStationsIDList": []}

    U_NEAR = "https://api.weather.com/v3/location/near"
    U_DAILY = "https://api.weather.com/v2/pws/dailysummary/7day"
    U_CUR = "https://api.weather.com/v2/pws/observations/current"
    U_FCST = "https://api.weather.com/v3/wx/forecast/daily/5day"

    agent = "RainMachine-WUnderground-Backup/1.0"
    timeout = 60

    _sniChecked = False
    _sniOk = False
    _status = None
    _transport = ""
    _auto = ""
    _autoKm = 0.0

    def isEnabledForLocation(self, timezone, lat, long):
        # Only the API key is required: the station is discovered on first run.
        k = self.params.get("apiKey")
        return WUndergroundBackup.parserEnabled and isinstance(k, str) and len(k.strip()) > 0

    def perform(self):
        self._rows = []
        self.params["_info"] = []
        self.params["_nearbyStationsIDList"] = []
        self.lastKnownError = ""
        self._status = None

        key = self.params.get("apiKey")
        if not isinstance(key, str) or not key.strip():
            self._fail("001")
            self._info(None)
            return
        key = key.strip()

        # WU station ids are uppercase; a lowercase id silently returns 204.
        sid = self.params.get("stationId")
        sid = sid.strip().upper() if isinstance(sid, str) and sid.strip() else None

        b = _Ssl.get()
        log.info("WU: python=%s sni=%s libssl=%s" % (sys.version.split()[0],
                 "yes" if self._sni() else "no", b.path if b else "none"))

        # An explicit station skips the lookup, saving one request per run.
        ranked = None if sid else self._nearby(key)

        # The forecast is geocoded from the controller location, so it works
        # before a station is chosen: the first refresh already shows data.
        gotF = self._fcst(key)

        if sid:
            self._auto = ""
            station, gotH = sid, self._hist(key, sid)
        else:
            station, gotH = self._pick(key, ranked)

        if gotH and gotF:
            self.lastKnownError = ""
        elif not gotH and not gotF:
            if not self.lastKnownError:
                self.lastKnownError = wuErr("103")
            log.error(self.lastKnownError)
        elif not gotH and not station:
            self.lastKnownError = wuErr("003")

        self._info(station)

    # ---- UI -------------------------------------------------------------
    # A weather service cannot style the RainMachine UI, with one exception:
    # generateTagFromDataType() renders a read-only LIST param via innerHTML,
    # while every other type goes through textContent and is escaped. So the
    # status block and the station picker are both list params.

    def _info(self, station):
        # PLAIN TEXT ONLY. A read-only list parameter is rendered with
        # innerHTML, so markup here would reach the page - but a settings
        # screen that fails to render cannot be used to enter the API key,
        # which is not a trade worth making for some colour.
        b = _Ssl.get()
        rows = ["Status: %s" % (self.lastKnownError or "OK")]
        if station and self._auto == station:
            rows.append("Station: %s (auto-selected, %.1f km)" % (station, self._autoKm))
        elif station:
            rows.append("Station: %s (set manually)" % station)
        else:
            rows.append("Station: none - leave stationId empty to auto-select")
        rows.append("Transport: %s" % (self._transport or "none succeeded"))
        rows.append("Device: Python %s, TLS SNI %s"
                    % (sys.version.split()[0], "yes" if self._sni() else "no"))
        rows.append("libssl: %s" % (b.path if b else "not loaded"))
        self.params["_info"] = rows
        self.params["_nearbyStationsIDList"] = self._rows

    # ---- transport ------------------------------------------------------

    def _sni(self):
        if not WUndergroundBackup._sniChecked:
            WUndergroundBackup._sniOk = bool(getattr(ssl, "HAS_SNI", False)) and hasattr(ssl, "SSLContext")
            WUndergroundBackup._sniChecked = True
        return WUndergroundBackup._sniOk

    def _chk(self, status):
        if status == 200:
            return
        self._status = status
        # 421 and 5xx are not definitive: another transport may still succeed.
        if status in (204, 400, 401, 403, 404, 429):
            raise ApiError(status)

    def _viaC(self, url):
        # Embedded hardware drops the odd handshake or read; one retry turns an
        # intermittent failure into a successful refresh.
        status = body = None
        for attempt in (1, 2):
            try:
                status, body = sniGet(url, self.timeout, self.agent)
                break
            except Exception, e:
                if attempt == 1:
                    time.sleep(1)
                    continue
                log.warning("WU: libssl transport failed: %s" % e)
                return None
        self._chk(status)
        if status != 200:
            log.warning("WU: HTTP %s" % status)
            return None
        self._transport = "ctypes+libssl"
        return body

    def _viaU(self, url):
        req = urllib2.Request(url, headers={"User-Agent": self.agent,
                                            "Accept": "application/json"})
        try:
            res = urllib2.urlopen(req, timeout=self.timeout)
            self._chk(res.getcode())          # 204 is a success status
            self._transport = "urllib2"
            return res.read()
        except urllib2.HTTPError, e:
            self._chk(e.code)
            log.warning("WU: HTTP %s" % e.code)
            return None
        except ApiError:
            raise
        except Exception, e:
            log.warning("WU: urllib2 failed: %s" % e)
            return None

    def _get(self, base, params):
        url = "?".join([base, urllib.urlencode(params)])
        for fetch in ([self._viaU, self._viaC] if self._sni() else [self._viaC, self._viaU]):
            try:
                body = fetch(url)
            except ApiError:
                raise
            except Exception:
                body = None
            if body:
                try:
                    return json.loads(body)
                except Exception:
                    i = url.find("apiKey=")
                    return self._fail("104", url if i < 0 else url[:i] + "apiKey=***")
        code = self._status if self._status else "103"
        if not (self._sni() or _Ssl.get() is not None):
            code = "100"
        return self._fail(code)

    def _fail(self, code, extra=""):
        self.lastKnownError = wuErr(code, extra)
        log.error(self.lastKnownError)
        return None

    # ---- data -----------------------------------------------------------

    def _nearby(self, key):
        s = self.settings
        try:
            d = self._get(self.U_NEAR, [
                ("geocode", "%s,%s" % (s.location.latitude, s.location.longitude)),
                ("product", "pws"), ("format", "json"), ("apiKey", key)])
            if not d:
                return None          # _get already recorded the real error
            loc = d["location"]
            g = lambda k: loc.get(k) or []
            ids, dist, qc, upd, lat, lon = (g("stationId"), g("distanceKm"), g("qcStatus"),
                                            g("updateTimeUtc"), g("latitude"), g("longitude"))
            at = lambda a, i: a[i] if i < len(a) else 0
            # location/near ranks purely by distance and happily returns stations
            # that stopped reporting months ago, so sort dead ones to the bottom.
            now = time.time()
            ranked = []
            for i, sid in enumerate(ids):
                if sid is None:
                    continue
                t, q = at(upd, i), at(qc, i)
                age = int((now - t) / 3600) if t else -1
                ranked.append((0 if (0 <= age <= 24 and q >= 0) else 1, at(dist, i), sid,
                               q, age, at(lat, i), at(lon, i)))
            ranked.sort()
            # List params are read-only text - there is no picker widget available
            # to a weather service, so the instructions go at the top of the list.
            if ranked:
                self._rows += [
                    "Leave stationId empty to use the closest working station.",
                    "To pick your own, copy an ID below (e.g. %s) into "
                    "stationId, then press Save." % ranked[0][2],
                    "Entries with an old timestamp have stopped reporting.",
                    "--- Nearby stations ---"]
            for stale, km, sid, q, age, la, lo in ranked:
                when = "no data" if age < 0 else ("%dh ago" % age if age < 48 else "%dd ago" % (age / 24))
                # Same shape as the stock parser, with freshness appended:
                #   KCAPLEAS247 (0.6km; lat=37.66, lon=-121.88) 1h ago
                self._rows.append(
                    "%s (%.1fkm; lat=%.2f, lon=%.2f) %s"
                    % (sid, km, la, lo, when + (", failed QC" if q < 0 else "")))
            return ranked
        except ApiError, e:
            self.lastKnownError = str(e)
            log.error(self.lastKnownError)
        except Exception, e:
            log.warning("WU: nearby lookup failed: %s" % e)
        return None

    def _pick(self, key, ranked):
        # No station set: nearest non-stale wins, but a station can look fresh
        # and still have no daily summaries, so each candidate is tried for real.
        if ranked is None:
            return None, False        # lookup failed; its own error is already set
        cand = [r for r in ranked if r[0] == 0] or [r for r in ranked if r[4] >= 0]
        if not cand:
            self._fail("002")
            return None, False
        # Prefer last run's choice so the source stays stable instead of drifting.
        prev = self._auto
        for row in [r for r in cand if r[2] == prev] + [r for r in cand if r[2] != prev]:
            sid = row[2]
            if self._hist(key, sid, False):
                # Never put informational text in lastKnownError: the web UI
                # treats any non-empty value as an error and renders it red.
                self._auto, self._autoKm, self.lastKnownError = sid, row[1], ""
                log.info("WU: auto-selected %s" % sid)
                return sid, True
            log.info("WU: %s returned no data, trying next" % sid)
        self._fail("003")
        return None, False

    def _hist(self, key, station, diagnose=True):
        try:
            d = self._get(self.U_DAILY, [("stationId", station), ("format", "json"),
                                         ("units", "m"), ("apiKey", key)])
            return self._pHist(d) if d else False
        except ApiError, e:
            self.lastKnownError = str(e)
            log.error(self.lastKnownError)
            if e.code == 204 and diagnose:
                self._why(key, station)
            return False
        except Exception, e:
            self._fail("105", str(e))
            return False

    def _why(self, key, station):
        # Separate "station does not exist" from "alive but no summaries yet".
        try:
            d = self._get(self.U_CUR, [("stationId", station), ("format", "json"),
                                       ("units", "m"), ("apiKey", key)])
            if d and (d.get("observations") or []):
                log.info("WU: %s is reporting but has no daily summaries yet." % station)
                return
        except Exception:
            pass
        log.error("WU: %s returned nothing - check the id." % station)

    def _pHist(self, data):
        today = rmCurrentDayTimestamp()
        yday = rmDeltaDayFromTimestamp(today, -1)
        lim = RMWeatherDataLimits()
        dt = RMParser.dataType
        got = False
        try:
            for obs in data.get("summaries") or []:
                epoch = obs.get("epoch")
                if epoch is None:
                    continue
                ts = rmGetStartOfDay(epoch)
                m = obs.get("metric") or {}
                rain = self._f(m.get("precipTotal"))
                if ts == yday:
                    wind = self._f(m.get("windspeedAvg"))
                    if wind is not None:
                        wind = wind / 3.6                       # km/h -> m/s
                    hi, lo = self._f(m.get("pressureMax")), self._f(m.get("pressureMin"))
                    if hi is not None:
                        hi = lim.sanitize(RMWeatherDataType.PRESSURE, hi / 10.0)
                    if lo is not None:
                        lo = lim.sanitize(RMWeatherDataType.PRESSURE, lo / 10.0)
                    sol = self._f(m.get("solarRadiationHigh"))
                    for k, v in ((dt.TEMPERATURE, self._f(m.get("tempAvg"))),
                                 (dt.MINTEMP, self._f(m.get("tempLow"))),
                                 (dt.MAXTEMP, self._f(m.get("tempHigh"))),
                                 (dt.RH, self._f(obs.get("humidityAvg"))),
                                 (dt.MINRH, self._f(obs.get("humidityLow"))),
                                 (dt.MAXRH, self._f(obs.get("humidityHigh"))),
                                 (dt.WIND, wind), (dt.RAIN, rain),
                                 (dt.DEWPOINT, self._f(m.get("dewptAvg"))),
                                 (dt.PRESSURE, (hi + lo) / 2.0 if (hi is not None and lo is not None) else None),
                                 (dt.SOLARRADIATION, sol * 0.0864 if sol is not None else None)):
                        self.addValue(k, ts, v, False)
                    got = True
                elif ts == today:
                    # today: RAIN only, so forecast values are not overwritten
                    self.addValue(dt.RAIN, ts, rain, False)
                    got = True
            if not got:
                self.lastKnownError = wuErr("004")
            return got
        except Exception, e:
            self._fail("105", str(e))
            return False

    def _fcst(self, key):
        s = self.settings
        try:
            d = self._get(self.U_FCST, [
                ("geocode", "%s,%s" % (s.location.latitude, s.location.longitude)),
                ("language", "en-US"), ("units", "m"), ("format", "json"), ("apiKey", key)])
            if not d:
                return False
            self._pFcst(d)
            return True
        except ApiError, e:
            self.lastKnownError = str(e)
            log.error(self.lastKnownError)
            return False
        except Exception, e:
            self._fail("106", str(e))
            return False

    def _pFcst(self, data):
        dp = (data.get("daypart") or [{}])[0] or {}
        g = lambda o, k: o.get(k) or []
        icon, rh, wind = g(dp, "iconCode"), g(dp, "relativeHumidity"), g(dp, "windSpeed")
        dew, pop, sky = g(dp, "temperatureDewPoint"), g(dp, "precipChance"), g(dp, "cloudCover")
        tmin, tmax, qpf = g(data, "temperatureMin"), g(data, "temperatureMax"), g(data, "qpf")
        dt = RMParser.dataType
        for i, t in enumerate(g(data, "validTimeUtc")):
            d, n = 2 * i, 2 * i + 1            # day part, night part
            w = self._avg(self._at(wind, d), self._at(wind, n))
            pd, pn = self._at(pop, d), self._at(pop, n)
            # SKYCOVER is a 0..1 fraction in RainMachine (rmLimits caps it at
            # 1); the API reports cloud cover as a percentage.
            sc = self._avg(self._at(sky, d), self._at(sky, n))
            if sc is not None:
                sc = sc / 100.0
            for k, v in ((dt.MINTEMP, self._at(tmin, i)), (dt.MAXTEMP, self._at(tmax, i)),
                         (dt.QPF, self._at(qpf, i)), (dt.MINRH, self._at(rh, d)),
                         (dt.MAXRH, self._at(rh, n)), (dt.WIND, w / 3.6 if w is not None else None),
                         (dt.DEWPOINT, self._avg(self._at(dew, d), self._at(dew, n))),
                         (dt.SKYCOVER, sc),
                         (dt.POP, max(pd, pn) if (pd is not None and pn is not None) else self._avg(pd, pn)),
                         (dt.CONDITION, self._cond(icon[d] if d < len(icon) else None))):
                if v is not None:
                    self.addValue(k, t, v, False)

    def _at(self, a, i):
        return self._f(a[i]) if i < len(a) else None

    def _avg(self, a, b):
        if a is not None and b is not None:
            return (a + b) / 2.0
        return a if a is not None else b

    def _f(self, v):
        try:
            return None if v is None else float(v)
        except:
            return None

    _COND = ("0,1,2 FunnelCloud|3,4,38 Thunderstorm|5,7,17,18 RainSnow|6 RainIce|"
             "8,10 FreezingRain|9,11,35 LightRain|12,40 HeavyRain|"
             "13,14,15,16,41,42,43,46 Snow|20 Fog|21 Haze|22 Smoke|23,24 Windy|"
             "25 IcePellets|26 FewClouds|27,28 MostlyCloudy|29,30 PartlyCloudy|"
             "31,32,33,34,36 Fair|37,47 ThunderstormInVicinity|39,45 RainShowers")

    def _cond(self, c):
        if c is None:
            return None
        for part in self._COND.split("|"):
            codes, name = part.split(" ")
            if str(c) in codes.split(","):
                return getattr(RMParser.conditionType, name)
        return RMParser.conditionType.Unknown
