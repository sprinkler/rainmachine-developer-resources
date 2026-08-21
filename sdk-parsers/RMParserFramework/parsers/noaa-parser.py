from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmTimeUtils import *
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
dt=RMParser.dataType
ct=RMParser.conditionType
cT=rmCurrentDayTimestamp
gD=rmGetStartOfDay
fT=rmTimestampFromDateAsStringWithOffset
gS=globalSettings
SSL_CTRL_SET_TLSEXT_HOSTNAME = 55
TLSEXT_NAMETYPE_host_name    = 0
SSL_RETRY_ERRORS = (2, 3, 5)
SSL_LIBS = ["/usr/lib/libssl.so.1.0.0","/lib/libssl.so.1.0.0","/usr/lib/libssl.so","libssl.so.1.0.0"]
CRYPTO_LIBS = [p.replace("libssl", "libcrypto") for p in SSL_LIBS]
class SNIError(Exception): pass
class SSLBinding(object):
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
 binding = SSLBinding.get()
 if binding is None:
  raise SNIError("libssl unavailable")
 rest = url.split("://", 1)[1]
 cut  = rest.find("/")
 host = rest[:cut] if cut >= 0 else rest
 path = rest[cut:] if cut >= 0 else "/"
 sock = socket.create_connection((host, 443), timeout)
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
  if s.SSL_ctrl(conn, SSL_CTRL_SET_TLSEXT_HOSTNAME,
     TLSEXT_NAMETYPE_host_name, host) != 1:
   raise SNIError("cannot set SNI hostname")
  if s.SSL_connect(conn) != 1:
   raise SNIError("handshake failed (err=%d)" % s.SSL_get_error(conn, -1))
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
   break
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
  try:
   expected = int(head.split("content-length:")[1].split("\r\n")[0].strip())
   if len(body) < expected:
    raise SNIError("truncated body (%d of %d bytes)" % (len(body), expected))
  except (ValueError, IndexError):
   pass
 return status, body
class SNIResponse(object):
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
 parserInterval = 6 * 3600
 params = {}
 agent = "RainMachine v2"
 timeout = 60
 _answered = False
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
  self._answered = False
  order = ([self.__viaUrllib, self.__viaCtypes] if (getattr(ssl,"HAS_SNI",False)and hasattr(ssl,"SSLContext"))
    else [self.__viaCtypes, self.__viaUrllib])
  for transport in order:
   try:
    response = transport(url, headers)
   except Exception:
    response = None
   if response is not None:
    return response
   if self._answered:
    break
  if not ((getattr(ssl,"HAS_SNI",False)and hasattr(ssl,"SSLContext")) or SSLBinding.get() is not None):
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
  pointsURL = "https://api.weather.gov/points/%s,%s" % (
   s.location.latitude, s.location.longitude)
  d = self.openURL(pointsURL)
  if d is None:
   self.lastKnownError = "Error: no grid point"
   log.error(self.lastKnownError)
   return
  try:
   points = json.loads(d.read())
   props = points.get("properties", {})
   hourlyURL = props.get("forecastHourly")
   dailyURL  = props.get("forecast")
   gridURL   = props.get("forecastGridData")
  except Exception, e:
   self.lastKnownError = "Error: bad grid point"
   log.error(self.lastKnownError)
   log.exception(e)
   return
  if not (hourlyURL and gridURL):
   self.lastKnownError = "Error: incomplete grid"
   log.error(self.lastKnownError)
   return
  hasHourly = self.getHourlyData(hourlyURL, gridURL)
  hasDaily  = self.getDailyData(dailyURL) if dailyURL else False
  if not hasHourly:
   self.clearValues()
  if self.parserDebug:
   log.debug(self.result)
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
  todayTimestamp = cT()
  maxDayTimestamp = todayTimestamp + gS.parserDataSizeInDays * 86400
  maxDayRH = {}
  minDayRH = {}
  for p in periods:
   ts = fT(p.get("startTime"))
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
    day = gD(ts)
    if day not in minDayRH or rh < minDayRH[day]:
     minDayRH[day] = rh
    if day not in maxDayRH or rh > maxDayRH[day]:
     maxDayRH[day] = rh
   if temp  is not None: self.addValue(dt.TEMPERATURE, ts, temp, False)
   if rh    is not None: self.addValue(dt.RH,          ts, rh,   False)
   if dew   is not None: self.addValue(dt.DEWPOINT,    ts, dew,  False)
   if wind  is not None: self.addValue(dt.WIND,        ts, wind, False)
   if pop   is not None: self.addValue(dt.POP,         ts, pop,  False)
   if sky   is not None: self.addValue(dt.SKYCOVER,    ts, sky / 100.0, False)
  for ts, qpf in qpfByHour.items():
   if ts < maxDayTimestamp:
    self.addValue(dt.QPF, ts, qpf, False)
  for day, value in minDayRH.items():
   self.addValue(dt.MINRH, day, value, False)
  for day, value in maxDayRH.items():
   self.addValue(dt.MAXRH, day, value, False)
  if self.parserDebug:
   with open("noaa-hourly-%s.json" % rmTimestampToDateAsString(todayTimestamp), "w") as f:
    json.dump(data, f, indent=2)
  return True
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
  todayTimestamp = cT()
  maxDayTimestamp = todayTimestamp + gS.parserDataSizeInDays * 86400
  for p in periods:
   ts = fT(p.get("startTime"))
   if ts is None or ts >= maxDayTimestamp:
    continue
   temp = self.__toFloat(p.get("temperature"))
   if temp is not None and p.get("temperatureUnit") == "F":
    temp = (temp - 32) * 5.0 / 9.0
   if p.get("isDaytime"):
    self.addValue(dt.MAXTEMP, ts, temp, False)
   else:
    self.addValue(dt.MINTEMP, ts, temp, False)
   icon = p.get("icon") or ""
   slug = icon.split("?")[0].rsplit("/", 1)[-1].split(",", 1)[0]
   if slug:
    self.addValue(dt.CONDITION, ts, self.conditionConvert(slug), False)
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
   ts = fT(base)
   if ts is None:
    continue
   if byHour:
    ts = ts - (ts % 3600)
   if item.get("value") is not None:
    result[ts] = self.__toFloat(item["value"])
  return result
 def __value(self, f):
  return self.__toFloat(f.get("value")) if isinstance(f,dict) else None
 def __parseWind(self, s):
  if not s: return None
  p=s.split()
  try: v=float(p[0])
  except: return None
  u=p[1].lower() if len(p)>1 else "mph"
  return v*0.44704 if u.startswith("mph") else v/3.6 if u.startswith("km") else v*0.514444 if u.startswith("kt") else None
 def __toFloat(self, v):
  try: return None if v is None else float(v)
  except: return None
 _C="bkn.MostlyCloudy|skc.Fair|few.FewClouds|sct.PartlyCloudy|ovc.Overcast|fg.Fog|smoke.Smoke|fzra.HeavyFreezingRain|ip.IcePellets|mix.FreezingRain|raip.RainIce|sleet.RainIce|hail.RainIce|rasn.RainSnow|shra.RainShowers|tsra.Thunderstorm|sn.Snow|showers.RainShowers|wind.Windy|shwrs.ShowersInVicinity|fzrara.HeavyFreezingRain|hi_tsra.ThunderstormInVicinity|ra1.LightRain|ra.HeavyRain|nsvrtsra.FunnelCloud|dust.Dust|mist.Haze|haze.Haze|hot.Hot|cold.Cold"
 def conditionConvert(self, s):
  for p in self._C.split("|"):
   k,v=p.split(".")
   if k in s: return getattr(ct,v)
  return ct.Unknown
if __name__=="__main__":
 import os
 class L: latitude=float(os.environ.get("RM_LAT","37.6"));longitude=float(os.environ.get("RM_LON","-121.8"));elevation=float(os.environ.get("RM_ELEVATION","80.0"))
 class S: location=L()
 p=NOAA();p.settings=S();p.perform();print len(p.result),p.lastKnownError
