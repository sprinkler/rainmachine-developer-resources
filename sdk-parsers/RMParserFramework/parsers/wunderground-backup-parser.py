from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmGetStartOfDay as gD,rmCurrentDayTimestamp as cT,rmDeltaDayFromTimestamp as dT
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType as W
import ctypes as C,os,socket as S,ssl,struct,sys,time,urllib,urllib2,json
L=["/usr/lib/libssl.so.1.0.0","/lib/libssl.so.1.0.0","/usr/lib/libssl.so.1.0.2","/usr/lib/libssl.so.1.1","/usr/lib/libssl.so","/system/lib/libssl.so","/system/lib64/libssl.so","libssl.so.1.0.0","libssl.so"]
class E(Exception):pass
class _Ssl(object):
 i=None;d=False
 @classmethod
 def get(cls):
  if cls.d:return None
  if cls.i is None:
   try:cls.i=_Ssl()
   except Exception,e:cls.d=True;log.warning("WU: no libssl: %s"%e);return None
  return cls.i
 def __init__(s):
  s.cr=s._l(1);s.lib=s._l(0)
  z=s.lib;v=C.c_void_p;i=C.c_int;q=C.c_long;c=C.c_char_p
  s.m=getattr(z,"SSLv23_client_method",None) or z.TLS_client_method;s.m.restype=v
  for n,a,r in(("SSL_CTX_new",[v],v),("SSL_CTX_free",[v],None),("SSL_new",[v],v),("SSL_free",[v],None),("SSL_set_fd",[v,i],i),("SSL_ctrl",[v,i,q,c],q),("SSL_connect",[v],i),("SSL_write",[v,c,i],i),("SSL_read",[v,c,i],i),("SSL_shutdown",[v],i),("SSL_get_error",[v,i],i)):
   f=getattr(z,n);f.argtypes=a
   if r:f.restype=r
  for n in("SSL_library_init","SSL_load_error_strings"):
   try:getattr(z,n)()
   except AttributeError:pass
 def _l(s,g):
  for n in L:
   m=n.replace("libssl","libcrypto") if g else n
   if m[0]=="/" and not os.path.exists(m):continue
   try:
    if g:return C.CDLL(m,mode=C.RTLD_GLOBAL)
    s.path=m;return C.CDLL(m)
   except Exception:pass
  raise E("no libssl")
def dch(b):
 o=[]
 while b:
  nl=b.find("\r\n")
  if nl<0:break
  try:x=int(b[:nl].split(";")[0].strip(),16)
  except ValueError:break
  if x==0:break
  o.append(b[nl+2:nl+2+x]);b=b[nl+2+x+2:]
 return "".join(o)
def sniGet(url,t,ua):
 b=_Ssl.get()
 if b is None:raise E("no libssl")
 r=url.split("://",1)[1];k=r.find("/");h=r[:k] if k>=0 else r;p=r[k:] if k>=0 else "/"
 so=S.create_connection((h,443),t);so.setblocking(1)
 try:
  tv=struct.pack("ll",int(t),0);so.setsockopt(S.SOL_SOCKET,S.SO_RCVTIMEO,tv);so.setsockopt(S.SOL_SOCKET,S.SO_SNDTIMEO,tv)
 except Exception:pass
 z=b.lib;ctx=cn=None
 try:
  ctx=z.SSL_CTX_new(b.m())
  if not ctx:raise E("ctx")
  cn=z.SSL_new(ctx)
  if not cn:raise E("new")
  if z.SSL_set_fd(cn,so.fileno())!=1:raise E("fd")
  if z.SSL_ctrl(cn,55,0,h)!=1:raise E("sni")
  if z.SSL_connect(cn)!=1:raise E("hs%d"%z.SSL_get_error(cn,-1))
  rq="GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\nAccept: application/json\r\nConnection: close\r\n\r\n"%(p,h,ua)
  n=0
  while n<len(rq):
   k=z.SSL_write(cn,rq[n:],len(rq)-n)
   if k<=0:raise E("wr")
   n+=k
  o=[];buf=C.create_string_buffer(16384);dl=time.time()+t
  while 1:
   k=z.SSL_read(cn,buf,16384)
   if k>0:o.append(buf.raw[:k]);continue
   if z.SSL_get_error(cn,k) in(2,3,5) and time.time()<dl:time.sleep(.1);continue
   break
  data="".join(o)
 finally:
  try:
   if cn:z.SSL_shutdown(cn);z.SSL_free(cn)
   if ctx:z.SSL_CTX_free(ctx)
  except Exception:pass
  try:so.close()
  except Exception:pass
 i=data.find("HTTP/1.")
 if i<0:raise E("no resp")
 data=data[i:]
 try:st=int(data.split(" ",2)[1])
 except Exception:raise E("bad st")
 sep=data.find("\r\n\r\n")
 if sep<0:return st,""
 hd=data[:sep].lower();bd=data[sep+4:]
 if "transfer-encoding: chunked" in hd:bd=dch(bd)
 elif "content-length:" in hd:
  try:
   w=int(hd.split("content-length:")[1].split("\r\n")[0].strip())
   if len(bd)<w:raise E("trunc")
  except (ValueError,IndexError):pass
 return st,bd
ERR = {
 "001": "No API key set",
 "002": "No nearby stations found",
 "003": "No nearby station returned data",
 "004": "No usable daily summaries",
 "100": "No SNI-capable transport on this device",
 "103": "Request failed on every available transport",
 "104": "Invalid or truncated JSON",
 "105": "Cannot parse station data",
 "106": "Cannot parse forecast data",
 204: "Station has no data - wrong ID or offline (key is valid)",
 400: "Bad request - check the Station ID",
 401: "API key rejected - regenerate it",
 403: "API key not authorized - register a PWS",
 404: "Station or endpoint not found",
 421: "Misdirected Request - TLS SNI rejected",
 429: "Rate limited - too many requests",
}
def wuErr(code, extra=""):
 t=ERR.get(code,"Unexpected failure")
 if isinstance(code,int) and code>=500:
  t = "Weather Underground server error"
 return "WU-%s: %s%s"%(code,t,(" (%s)"%extra) if extra else "")
class ApiError(Exception):
 def __init__(self, code, extra=""):
  Exception.__init__(self, wuErr(code, extra))
  self.code = code
dt = RMParser.dataType
ct = RMParser.conditionType
class WUndergroundBackup(RMParser):
 parserName = "WUnderground Backup"
 parserDescription = "Weather Underground PWS obs + forecast for controllers without TLS SNI"
 parserForecast = True
 parserHistorical = True
 parserEnabled = False
 parserDebug = False
 parserID = "wundergroundbackup"
 parserInterval = 3600
 params = {"_info":[],"apiKey":None,"stationId":None,"_nearbyStationsIDList":[]}
 U_NEAR = "https://api.weather.com/v3/location/near"
 U_DAILY = "https://api.weather.com/v2/pws/dailysummary/7day"
 U_CUR = "https://api.weather.com/v2/pws/observations/current"
 U_FCST = "https://api.weather.com/v3/wx/forecast/daily/5day"
 agent = "RainMachine-WUnderground-Backup/1.0"
 timeout = 60
 _sc=False;_so=False;_status=None;_tr="";_auto="";_km=0.0
 def isEnabledForLocation(self, timezone, lat, long):
  k=self.params.get("apiKey")
  return self.parserEnabled and isinstance(k,str) and len(k.strip())>0
 def perform(self):
  self._rows=[];self.params["_info"]=[];self.params["_nearbyStationsIDList"]=[];self.lastKnownError="";self._status=None
  key=self.params.get("apiKey")
  if not isinstance(key, str) or not key.strip():
   self._fail("001")
   self._info(None)
   return
  key=key.strip()
  sid=self.params.get("stationId")
  sid=sid.strip().upper() if isinstance(sid,str) and sid.strip() else None
  b=_Ssl.get()
  log.info("WU: py=%s sni=%s ssl=%s"%(sys.version.split()[0],
    "yes" if self._sni() else "no", b.path if b else "none"))
  ranked=None if sid else self._nearby(key)
  gotF=self._fcst(key)
  if sid:
   self._auto = ""
   station,gotH=sid,self._hist(key,sid)
  else:
   station,gotH=self._pick(key,ranked)
  if gotH and gotF:
   self.lastKnownError=""
  elif not gotH and not gotF:
   if not self.lastKnownError:
    self.lastKnownError=wuErr("103")
   log.error(self.lastKnownError)
  elif not gotH and not station:
   self.lastKnownError=wuErr("003")
  self._info(station)
 def _info(self, station):
  rows=["Status: %s"%(self.lastKnownError or "OK")]
  if station and self._auto==station:
   rows.append("Station: %s (auto, %.1fkm)"%(station,self._km))
  elif station:
   rows.append("Station: %s (set manually)"%station)
  else:
   rows.append("Station: none - leave stationId empty")
  rows.append("Transport: %s"%(self._tr or "none succeeded"))
  self.params["_info"] = rows
  self.params["_nearbyStationsIDList"] = self._rows
 def _sni(self):
  if not self._sc:
   self._so=bool(getattr(ssl,"HAS_SNI",False)) and hasattr(ssl,"SSLContext")
   self._sc=True
  return self._so
 def _chk(self, status):
  if status == 200:
   return
  self._status=status
  if status in (204, 400, 401, 403, 404, 429):
   raise ApiError(status)
 def _viaC(self, url):
  status=body=None
  for attempt in (1, 2):
   try:
    status,body=sniGet(url,self.timeout,self.agent)
    break
   except Exception, e:
    if attempt == 1:
     time.sleep(1)
     continue
    log.warning("WU: ctypes failed: %s"%e)
    return None
  self._chk(status)
  if status != 200:
   log.warning("WU: HTTP %s"%status)
   return None
  self._tr = "ctypes"
  return body
 def _viaU(self, url):
  req=urllib2.Request(url,headers={"User-Agent":self.agent,"Accept":"application/json"})
  try:
   res=urllib2.urlopen(req,timeout=self.timeout)
   self._chk(res.getcode())
   self._tr = "urllib2"
   return res.read()
  except urllib2.HTTPError, e:
   self._chk(e.code)
   log.warning("WU: HTTP %s"%e.code)
   return None
  except ApiError:
   raise
  except Exception, e:
   log.warning("WU: urllib2 failed: %s"%e)
   return None
 def _get(self, base, params):
  url="?".join([base,urllib.urlencode(params)])
  for fetch in ([self._viaU, self._viaC] if self._sni() else [self._viaC, self._viaU]):
   try:
    body=fetch(url)
   except ApiError:
    raise
   except Exception:
    body = None
   if body:
    try:
     return json.loads(body)
    except Exception:
     i=url.find("apiKey=")
     return self._fail("104",url if i<0 else url[:i]+"apiKey=***")
  code=self._status if self._status else "103"
  if not (self._sni() or _Ssl.get() is not None):
   code = "100"
  return self._fail(code)
 def _fail(self, code, extra=""):
  self.lastKnownError=wuErr(code,extra)
  log.error(self.lastKnownError)
  return None
 def _nearby(self, key):
  s = self.settings
  try:
   d=self._get(self.U_NEAR,[("geocode","%s,%s"%(s.location.latitude,s.location.longitude)),("product","pws"),("format","json"),("apiKey",key)])
   if not d:
    return None
   loc=d["location"]
   g=lambda k:loc.get(k)or[]
   ids,dist,qc,upd,lat,lon=g("stationId"),g("distanceKm"),g("qcStatus"),g("updateTimeUtc"),g("latitude"),g("longitude")
   at=lambda a,i:a[i]if i<len(a)else 0
   now=time.time()
   ranked=[]
   for i,sid in enumerate(ids):
    if sid is None:
     continue
    t,q=at(upd,i),at(qc,i)
    age=int((now-t)/3600) if t else -1
    ranked.append((0 if (0<=age<=24 and q>=0) else 1,at(dist,i),sid,q,age,at(lat,i),at(lon,i)))
   ranked.sort()
   if ranked:
    self._rows += [
     "Leave stationId empty for auto.",
     "Copy an ID below (e.g. %s) into stationId." % ranked[0][2],
     "Old entries stopped reporting.",
     "--- Stations ---"]
   for stale,km,sid,q,age,la,lo in ranked:
    when="no data" if age<0 else("%dh ago"%age if age<48 else"%dd ago"%(age/24))
    self._rows.append(
     "%s (%.1fkm; lat=%.2f, lon=%.2f) %s"
     %(sid,km,la,lo,when+(", failed QC" if q<0 else "")))
   return ranked
  except ApiError, e:
   self.lastKnownError = str(e)
   log.error(self.lastKnownError)
  except Exception, e:
   log.warning("WU: nearby failed: %s"%e)
  return None
 def _pick(self, key, ranked):
  if ranked is None:
   return None, False
  cand=[r for r in ranked if r[0]==0] or [r for r in ranked if r[4]>=0]
  if not cand:
   self._fail("002")
   return None, False
  prev=self._auto
  for row in [r for r in cand if r[2]==prev] + [r for r in cand if r[2]!=prev]:
   sid=row[2]
   if self._hist(key, sid, False):
    self._auto,self._km,self.lastKnownError=sid,row[1],""
    return sid, True
   log.info("WU: %s empty, next"%sid)
  self._fail("003")
  return None, False
 def _hist(self, key, station, diagnose=True):
  try:
   d=self._get(self.U_DAILY,[("stationId",station),("format","json"),("units","m"),("apiKey",key)])
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
  try:
   d=self._get(self.U_CUR,[("stationId",station),("format","json"),("units","m"),("apiKey",key)])
   if d and(d.get("observations")or[]):log.info("WU: %s reports, no summaries yet."%station);return
  except Exception:
   pass
  log.error("WU: %s returned nothing - check the id."%station)
 def _pHist(self, data):
  f = self._f
  today=cT()
  yday=dT(today,-1)
  lim=RMWeatherDataLimits()
  got=False
  try:
   for obs in data.get("summaries") or []:
    epoch=obs.get("epoch")
    if epoch is None:
     continue
    ts=gD(epoch)
    m=obs.get("metric") or {}
    rain=f(m.get("precipTotal"))
    if ts == yday:
     wind=f(m.get("windspeedAvg"))
     if wind is not None:wind=wind/3.6
     hi,lo=f(m.get("pressureMax")),f(m.get("pressureMin"))
     if hi is not None:hi=lim.sanitize(W.PRESSURE,hi/10.0)
     if lo is not None:lo=lim.sanitize(W.PRESSURE,lo/10.0)
     sol=f(m.get("solarRadiationHigh"))
     for k, v in ((dt.TEMPERATURE, f(m.get("tempAvg"))),
        (dt.MINTEMP, f(m.get("tempLow"))),
        (dt.MAXTEMP, f(m.get("tempHigh"))),
        (dt.RH, f(obs.get("humidityAvg"))),
        (dt.MINRH, f(obs.get("humidityLow"))),
        (dt.MAXRH, f(obs.get("humidityHigh"))),
        (dt.WIND, wind), (dt.RAIN, rain),
        (dt.DEWPOINT, f(m.get("dewptAvg"))),
        (dt.PRESSURE,(hi+lo)/2.0 if(hi is not None and lo is not None)else None),
        (dt.SOLARRADIATION,sol*0.0864 if sol is not None else None)):
      self.addValue(k, ts, v, False)
     got = True
    elif ts == today:
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
   d=self._get(self.U_FCST,[("geocode","%s,%s"%(s.location.latitude,s.location.longitude)),("language","en-US"),("units","m"),("format","json"),("apiKey",key)])
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
  at = self._at
  ag = self._avg
  dp=(data.get("daypart")or[{}])[0] or {}
  g=lambda o,k:o.get(k)or[]
  icon,rh,wind=g(dp,"iconCode"),g(dp,"relativeHumidity"),g(dp,"windSpeed")
  dew,pop,sky=g(dp,"temperatureDewPoint"),g(dp,"precipChance"),g(dp,"cloudCover")
  tmin,tmax,qpf=g(data,"temperatureMin"),g(data,"temperatureMax"),g(data,"qpf")
  for i,t in enumerate(g(data,"validTimeUtc")):
   d,n=2*i,2*i+1
   w=ag(at(wind,d),at(wind,n))
   pd,pn=at(pop,d),at(pop,n)
   sc=ag(at(sky,d),at(sky,n))
   if sc is not None:
    sc=sc/100.0
   for k, v in ((dt.MINTEMP, at(tmin, i)), (dt.MAXTEMP, at(tmax, i)),
      (dt.QPF, at(qpf, i)), (dt.MINRH, at(rh, d)),
      (dt.MAXRH, at(rh, n)), (dt.WIND,w/3.6 if w is not None else None),
      (dt.DEWPOINT, ag(at(dew, d), at(dew, n))),
      (dt.SKYCOVER, sc),
      (dt.POP,max(pd,pn) if(pd is not None and pn is not None)else ag(pd,pn)),
      (dt.CONDITION, self._cond(icon[d] if d < len(icon) else None))):
    if v is not None:
     self.addValue(k, t, v, False)
 def _at(self, a, i):
  return self._f(a[i]) if i<len(a) else None
 def _avg(self, a, b):
  if a is not None and b is not None:
   return (a+b)/2.0
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
  if c is None:return None
  for part in self._COND.split("|"):
   codes,name=part.split(" ")
   if str(c) in codes.split(","):
    return getattr(ct, name)
  return ct.Unknown

