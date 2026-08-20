from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmGetStartOfDay, rmCurrentDayTimestamp, rmDeltaDayFromTimestamp
from RMDataFramework.rmLimits import RMWeatherDataLimits
from RMDataFramework.rmWeatherData import RMWeatherDataType
import ctypes as C,os,socket as S,ssl,struct,sys,time,urllib,urllib2,json
L=["/usr/lib/libssl.so.1.0.0","/lib/libssl.so.1.0.0","/usr/lib/libssl.so.1.0.2","/usr/lib/libssl.so.1.1","/usr/lib/libssl.so","/system/lib/libssl.so","/system/lib64/libssl.so","libssl.so.1.0.0","libssl.so"]
class E(Exception):pass
class SSLBinding(object):
 i=None;d=False
 @classmethod
 def get(cls):
  if cls.d:return None
  if cls.i is None:
   try:cls.i=SSLBinding()
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
 b=SSLBinding.get()
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

class SNIResponse(object):
 def __init__(self, data, status):
  self.data = data
  self.status = status
 def read(self):
  return self.data
 def getcode(self):
  return self.status
 def close(self):
  pass
dt = RMParser.dataType
ct = RMParser.conditionType
cT = rmCurrentDayTimestamp
dT = rmDeltaDayFromTimestamp
gD = rmGetStartOfDay
W = RMWeatherDataType
class WUndergroundV2(RMParser):
 parserName = "WUnderground V2 Parser"
 parserDescription = "Weather Underground PWS obs + forecast"
 parserForecast = True
 parserHistorical = True
 parserEnabled = False
 parserDebug = False
 parserID = "wundergroundv2"
 parserInterval = 3600
 params = {"apiKey":None,"stationId":None,"_nearbyStationsIDList":[]}
 apiLocationURL = "https://api.weather.com/v3/location/near"
 apiHistoricalURL = "https://api.weather.com/v2/pws/dailysummary/7day"
 apiForecastURL = "https://api.weather.com/v3/wx/forecast/daily/5day"
 def isEnabledForLocation(self, timezone, lat, long):
  k=self.params.get("apiKey")
  return self.parserEnabled and isinstance(k,str) and len(k)>0
 agent = "RainMachine-WUndergroundV2/1.0"
 timeout = 60
 _answered=False;_sc=False;_sa=False;_autoSt=[]
 def _sni(self):
  if not self._sc:
   self._sa=bool(getattr(ssl,"HAS_SNI",False)) and hasattr(ssl,"SSLContext")
   self._sc=True
  return self._sa
 def __vu(self, url):
  req=urllib2.Request(url,headers={"User-Agent":self.agent,"Accept":"application/json"})
  try:
   res=urllib2.urlopen(req,timeout=self.timeout)
   return SNIResponse(res.read(),res.getcode())
  except urllib2.HTTPError,e:
   log.warning("WUV2: HTTP %s from %s"%(e.code,self.__su(url)))
  except Exception,e:
   log.warning("WUV2: urllib2 failed: %s"%e)
  return None
 def __vc(self, url):
  for attempt in (1,2):
   try:
    status,body=sniGet(url,self.timeout,self.agent)
   except Exception,e:
    if attempt==1:
     time.sleep(1)
     continue
    log.warning("WUV2: ctypes failed: %s"%e)
    return None
   if status!=200:
    log.warning("WUV2: HTTP %s from %s"%(status,self.__su(url)))
    self._answered=True
    return None
   return SNIResponse(body,status)
  return None
 def __su(self, url):
  at=url.find("apiKey=")
  return url if at<0 else url[:at]+"apiKey=***"
 def openURL(self, url, params=None, encodeParameters=True, headers={}):
  if params:
   url="?".join([url,urllib.urlencode(params) if encodeParameters else params])
  self._answered=False
  order=([self.__vu,self.__vc] if self._sni() else [self.__vc,self.__vu])
  for tr in order:
   try:
    r=tr(url)
   except Exception:
    r=None
   if r is not None:
    return r
   if self._answered:
    break
  if not (self._sni() or SSLBinding.get() is not None):
   self.lastKnownError="Error: no SNI-capable transport on this device - cannot reach api.weather.com"
  else:
   self.lastKnownError="Error: request failed on every available transport"
  log.error(self.lastKnownError)
  return None
 def perform(self):
  self.params["_nearbyStationsIDList"]=[]
  self.lastKnownError=""
  apiKey=self.params.get("apiKey")
  stationId=self.params.get("stationId")
  if not isinstance(apiKey,str) or not apiKey:
   self.lastKnownError="Error: No API Key provided."
   log.error(self.lastKnownError)
   return
  self.__gn(apiKey)
  if not isinstance(stationId,str) or not stationId:
   stationId=self._autoPick(apiKey)
   if stationId:
    self.lastKnownError=""
    self.params["_nearbyStationsIDList"].insert(0,"Station: %s (auto-selected, %.1f km)"%(stationId,self._autoKm))
   else:
    self.lastKnownError="Error: No nearby station with data - set a Station ID."
    log.error(self.lastKnownError)
    return
  hasHistorical=self.__gh(apiKey,stationId)
  hasForecast=self.__gf(apiKey)
  if not hasHistorical and not hasForecast:
   self.lastKnownError="Error: No data received."
   log.error(self.lastKnownError)
  elif not hasHistorical:
   log.warning("WUV2: no historical data.")
  elif not hasForecast:
   log.warning("WUV2: no forecast data.")
  else:
   log.info("WUV2: historical and forecast data retrieved.")
 def __gn(self, apiKey):
  s=self.settings
  try:
   d=self.openURL(self.apiLocationURL,[("geocode","%s,%s"%(s.location.latitude,s.location.longitude)),("product","pws"),("format","json"),("apiKey",str(apiKey))])
   if d is None:
    log.warning("WUV2: cannot fetch nearby stations.")
    return
   self.__pn(json.loads(d.read()))
  except Exception,e:
   log.warning("WUV2: nearby lookup failed: %s"%e)
 def __pn(self, data):
  try:
   loc=data["location"]
   ids=loc.get("stationId",[]) or []
   lats=loc.get("latitude",[]) or []
   lons=loc.get("longitude",[]) or []
   dist=loc.get("distanceKm",[]) or []
   stations=[]
   for i,sid in enumerate(ids):
    if sid is None:
     continue
    stations.append((sid,lats[i],lons[i],dist[i]))
   stations.sort(key=lambda x:x[3])
   for sid,la,lo,d in stations:
    self.params["_nearbyStationsIDList"].append("%s (%.1fkm; lat=%.2f, lon=%.2f)"%(sid,d,la,lo))
   if stations:
    self._autoSt=stations
  except Exception,e:
   log.warning("WUV2: nearby parse failed: %s"%e)
 def _autoPick(self, apiKey):
  for sid,la,lo,d in self._autoSt:
   if self.__gh(apiKey,sid):
    self._autoKm=d
    return sid
  return None
 def __gh(self, apiKey, stationId):
  try:
   d=self.openURL(self.apiHistoricalURL,[("stationId",str(stationId)),("format","json"),("units","m"),("apiKey",str(apiKey))])
   if d is None:
    self.lastKnownError="Error: Cannot download historical data."
    log.warning(self.lastKnownError)
    return False
   return self.__ph(json.loads(d.read()))
  except Exception,e:
   self.lastKnownError="Error: Cannot get historical data."
   log.error(self.lastKnownError)
   return False
 def __ph(self, data):
  today=cT();yday=dT(today,-1);lim=RMWeatherDataLimits();got=False
  f=self.__f
  try:
   for obs in data.get("summaries",[]):
    epoch=obs.get("epoch")
    if epoch is None:
     continue
    ts=gD(epoch)
    m=obs.get("metric") or {}
    temperature=f(m.get("tempAvg"));mintemp=f(m.get("tempLow"));maxtemp=f(m.get("tempHigh"))
    rh=f(obs.get("humidityAvg"));minrh=f(obs.get("humidityLow"));maxrh=f(obs.get("humidityHigh"))
    dewpoint=f(m.get("dewptAvg"));wind=f(m.get("windspeedAvg"));rain=f(m.get("precipTotal"))
    if wind is not None:wind=wind/3.6
    maxpressure=f(m.get("pressureMax"));minpressure=f(m.get("pressureMin"))
    if maxpressure is not None:maxpressure=lim.sanitize(W.PRESSURE,maxpressure/10.0)
    if minpressure is not None:minpressure=lim.sanitize(W.PRESSURE,minpressure/10.0)
    pressure=(maxpressure+minpressure)/2.0 if(maxpressure is not None and minpressure is not None) else None
    if ts==yday:
     solarRaw=f(m.get("solarRadiationHigh"))
     solar=solarRaw*0.0864 if solarRaw is not None else None
     for k,v in((dt.TEMPERATURE,temperature),(dt.MINTEMP,mintemp),(dt.MAXTEMP,maxtemp),(dt.RH,rh),(dt.MINRH,minrh),(dt.MAXRH,maxrh),(dt.WIND,wind),(dt.RAIN,rain),(dt.DEWPOINT,dewpoint),(dt.PRESSURE,pressure),(dt.SOLARRADIATION,solar)):
      self.addValue(k,ts,v,False)
     got=True
    elif ts==today:
     self.addValue(dt.RAIN,ts,rain,False)
     got=True
   return got
  except Exception,e:
   self.lastKnownError="Warning: Failed to parse historical data."
   log.error(self.lastKnownError)
   return False
 def __gf(self, apiKey):
  s=self.settings
  try:
   d=self.openURL(self.apiForecastURL,[("geocode","%s,%s"%(s.location.latitude,s.location.longitude)),("language","en-US"),("units","m"),("format","json"),("apiKey",str(apiKey))])
   if d is None:
    self.lastKnownError="Error: Cannot download forecast data."
    log.error(self.lastKnownError)
    return False
   data=json.loads(d.read())
   if not data.get("daypart"):
    self.lastKnownError="Error: Forecast response has no daypart data."
    log.error(self.lastKnownError)
    return False
   self.__pf(data)
   return True
  except Exception,e:
   self.lastKnownError="Error: Cannot get forecast data (%s)."%e
   log.error(self.lastKnownError)
   return False
 def __pf(self, data):
  dp=(data.get("daypart")or[{}])[0] or {}
  g=lambda o,k:o.get(k)or[]
  icon,rh,wspd=g(dp,"iconCode"),g(dp,"relativeHumidity"),g(dp,"windSpeed")
  dew,popL,sky=g(dp,"temperatureDewPoint"),g(dp,"precipChance"),g(dp,"cloudCover")
  ts,mi,ma,qpf=g(data,"validTimeUtc"),g(data,"temperatureMin"),g(data,"temperatureMax"),g(data,"qpf")
  f=self.__f
  at=lambda a,i:a[i]if i<len(a)else None
  for i,t in enumerate(ts):
   ni=2*i;di=2*i+1
   minrh=f(at(rh,ni));maxrh=f(at(rh,di))
   wN=f(at(wspd,ni));wD=f(at(wspd,di))
   wind=None
   if wN is not None and wD is not None:wind=(wN+wD)/2.0/3.6
   elif wD is not None:wind=wD/3.6
   elif wN is not None:wind=wN/3.6
   dN=f(at(dew,ni));dD=f(at(dew,di))
   dewpoint=None
   if dN is not None and dD is not None:dewpoint=(dN+dD)/2.0
   elif dD is not None:dewpoint=dD
   elif dN is not None:dewpoint=dN
   pN=f(at(popL,ni));pD=f(at(popL,di))
   pop=None
   if pN is not None and pD is not None:pop=max(pN,pD)
   elif pD is not None:pop=pD
   elif pN is not None:pop=pN
   sN=f(at(sky,ni));sD=f(at(sky,di))
   skycover=None
   if sN is not None and sD is not None:skycover=(sN+sD)/2.0
   elif sD is not None:skycover=sD
   elif sN is not None:skycover=sN
   if skycover is not None:skycover=skycover/100.0
   condition=self.__cc(at(icon,ni))
   for k,v in((dt.MINTEMP,f(at(mi,i))),(dt.MAXTEMP,f(at(ma,i))),(dt.MINRH,minrh),(dt.MAXRH,maxrh),(dt.WIND,wind),(dt.QPF,f(at(qpf,i))),(dt.CONDITION,condition),(dt.DEWPOINT,dewpoint),(dt.POP,pop),(dt.SKYCOVER,skycover)):
    if v is not None:
     self.addValue(k,t,v,False)
 _COND="0,1,2 FunnelCloud|3,4,38 Thunderstorm|5,7,17,18 RainSnow|6 RainIce|8,10 FreezingRain|9,11,35 LightRain|12,40 HeavyRain|13,14,15,16,41,42,43,46 Snow|20 Fog|21 Haze|22 Smoke|23,24 Windy|25 IcePellets|26 FewClouds|27,28 MostlyCloudy|29,30 PartlyCloudy|31,32,33,34,36 Fair|37,47 ThunderstormInVicinity|39,45 RainShowers"
 def __cc(self, c):
  if c is None:return None
  for part in self._COND.split("|"):
   codes,name=part.split(" ")
   if str(c) in codes.split(","):
    return getattr(ct,name)
  return ct.Unknown
 def __f(self, value):
  try:
   return None if value is None else float(value)
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

