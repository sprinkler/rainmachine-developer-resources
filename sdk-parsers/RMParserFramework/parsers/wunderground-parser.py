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
W = RMWeatherDataType
gD = rmGetStartOfDay
cT = rmCurrentDayTimestamp
dT = rmDeltaDayFromTimestamp
class WUnderground(RMParser):
 parserName = "WUnderground Parser"
 parserDescription = "Weather Underground PWS obs + forecast"
 parserForecast = True
 parserHistorical = True
 parserEnabled = False
 parserDebug = False
 parserInterval = 21600
 params = {"apiKey":None,"useCustomStation":False,"customStationName":None,"_nearbyStationsIDList":[],"_airportStationsIDList":[],"_apiForecastDays":5}
 apiLocationURL = "https://api.weather.com/v3/location/near?"
 apiStationSummaryURL = "https://api.weather.com/v2/pws/dailysummary/7day?"
 apiForecastURL = "https://api.weather.com/v3/wx/forecast/daily/%dday" % params["_apiForecastDays"]
 agent = "RainMachine-WUnderground/1.0"
 timeout = 60
 _answered=False;_sc=False;_sa=False
 def isEnabledForLocation(self, timezone, lat, long):
  return self.parserEnabled
 def _sni(self):
  if not self._sc:
   self._sa=bool(getattr(ssl,"HAS_SNI",False)) and hasattr(ssl,"SSLContext")
   self._sc=True
  return self._sa
 def __su(self, url):
  at=url.find("apiKey=")
  return url if at<0 else url[:at]+"apiKey=***"
 def __vu(self, url, agent):
  req=urllib2.Request(url,headers={"User-Agent":agent,"Accept":"*/*"})
  try:
   res=urllib2.urlopen(req,timeout=self.timeout)
   return SNIResponse(res.read(),res.getcode())
  except urllib2.HTTPError,e:
   log.warning("WU: HTTP %s from %s"%(e.code,self.__su(url)))
  except Exception,e:
   log.warning("WU: urllib2 failed: %s"%e)
  return None
 def __vc(self, url, agent):
  for attempt in (1,2):
   try:
    status,body=sniGet(url,self.timeout,agent)
   except S.gaierror,e:
    log.warning("WU: cannot resolve host: %s"%e)
    return None
   except Exception,e:
    if attempt==1:
     time.sleep(1)
     continue
    log.warning("WU: ctypes failed: %s"%e)
    return None
   if status!=200:
    log.warning("WU: HTTP %s from %s"%(status,self.__su(url)))
    self._answered=True
    return None
   return SNIResponse(body,status)
  return None
 def openURL(self, url, params=None, encodeParameters=True, headers={}):
  if params:
   url="?".join([url,urllib.urlencode(params) if encodeParameters else params])
  agent=headers.get("User-Agent",self.agent)
  self._answered=False
  order=([self.__vu,self.__vc] if self._sni() else [self.__vc,self.__vu])
  for tr in order:
   try:
    r=tr(url,agent)
   except Exception:
    r=None
   if r is not None:
    return r
   if self._answered:
    break
  if not (self._sni() or SSLBinding.get() is not None):
   self.lastKnownError="Error: no SNI-capable transport on this device - cannot reach api.weather.com"
  else:
   self.lastKnownError="Error: Can not open url"
  log.error(self.lastKnownError)
  return None
 def perform(self):
  self.params["_nearbyStationsIDList"]=[]
  self.params["_airportStationsIDList"]=[]
  self.lastKnownError=""
  apiKey=self.params.get("apiKey")
  useCustomStation=self.params.get("useCustomStation",False)
  stationName=self.params.get("customStationName")
  if not(isinstance(apiKey,str) and apiKey):
   self.lastKnownError="Error: No API Key provided."
   log.error(self.lastKnownError)
   return
  self.__gnp(apiKey)
  self.__gna(apiKey)
  hasForecastData=self.__gf(apiKey)
  hasStationData=False
  if useCustomStation:
   if not(isinstance(stationName,str) and stationName):
    self.lastKnownError="Warning: Use Nearby Stations is enabled but no station name specified."
    log.error(self.lastKnownError)
   else:
    for stationName in [n.strip() for n in stationName.split(",") if n.strip()]:
     hasStationData=self.__gs(apiKey,stationName)
     if hasStationData:
      break
    if not hasStationData:
     self.lastKnownError="Error: No observed data received from stations."
     log.error(self.lastKnownError)
    else:
     self.lastKnownError=""
     log.info("WU: station data retrieved for %s"%stationName)
  if not hasForecastData:
   self.lastKnownError="Warning: No Forecast data received."
   if not hasStationData:
    self.lastKnownError="Error: No forecast or station data received."
   log.error(self.lastKnownError)
  else:
   log.info("WU: forecast data retrieved.")
 def __gnp(self, apiKey):
  s=self.settings
  try:
   d=self.openURL(self.apiLocationURL+"geocode=%s,%s&product=pws&format=json&apiKey=%s"%(s.location.latitude,s.location.longitude,str(apiKey)))
   if d is None:
    self.lastKnownError="Cannot download nearby pws stations"
    log.error(self.lastKnownError)
   self.__pns(json.loads(d.read()))
  except Exception,e:
   self.lastKnownError="Error: Cannot get nearby pws stations"
   log.error(self.lastKnownError)
 def __gna(self, apiKey):
  s=self.settings
  try:
   d=self.openURL(self.apiLocationURL+"geocode=%s,%s&product=airport&format=json&apiKey=%s"%(s.location.latitude,s.location.longitude,str(apiKey)))
   if d is None:
    self.lastKnownError="Error: Cannot download nearby airport stations"
    log.error(self.lastKnownError)
   self.__pns(json.loads(d.read()))
  except Exception,e:
   self.lastKnownError="Error: Cannot get airport stations"
   log.error(self.lastKnownError)
 def __pns(self, data):
  loc=data["location"]
  ids=loc.get("stationId",None)
  pws=True
  if ids is None:
   pws=False
   ids=loc.get("icaoCode",None)
  lats=loc["latitude"];lons=loc["longitude"];dist=loc["distanceKm"]
  st=[]
  for i,sid in enumerate(ids):
   if sid is None:
    continue
   st.append((sid,lats[i],lons[i],dist[i]))
  st=sorted(st,key=lambda x:x[3])
  target=self.params["_nearbyStationsIDList"] if pws else self.params["_airportStationsIDList"]
  for sid,la,lo,d in st:
   target.append("%s (%.1fkm; lat=%.2f, lon=%.2f)"%(sid,d,la,lo))
 def __gs(self, apiKey, stationName):
  try:
   d=self.openURL(self.apiStationSummaryURL+"stationId=%s&format=json&units=m&apiKey=%s"%(str(stationName),str(apiKey)))
   if d is None:
    self.lastKnownError="Cannot download station data"
    log.error(self.lastKnownError)
    return False
   return self.__ps(json.loads(d.read()))
  except Exception,e:
   self.lastKnownError="Error: Cannot get station data"
   log.error(self.lastKnownError)
   return False
 def __ps(self, data):
  today=cT();yday=dT(today,-1);l=RMWeatherDataLimits();got=False
  f=self.__f
  try:
   for obs in data["summaries"]:
    ts=gD(obs.get("epoch",None))
    m=obs["metric"]
    temperature=f(m["tempAvg"]);mintemp=f(m["tempLow"]);maxtemp=f(m["tempHigh"])
    rh=f(obs["humidityAvg"]);minrh=f(obs["humidityLow"]);maxrh=f(obs["humidityHigh"])
    dewpoint=f(m["dewptAvg"]);wind=f(m["windspeedAvg"])
    if wind is not None:wind=wind/3.6
    maxpressure=f(m["pressureMax"]);minpressure=f(m["pressureMin"])
    if maxpressure is not None:maxpressure=l.sanitize(W.PRESSURE,maxpressure/10.0)
    if minpressure is not None:minpressure=l.sanitize(W.PRESSURE,minpressure/10.0)
    pressure=(maxpressure+minpressure)/2.0 if(maxpressure is not None and minpressure is not None) else None
    rain=f(m["precipTotal"])
    if ts==yday:
     for k,v in((dt.TEMPERATURE,temperature),(dt.MINTEMP,mintemp),(dt.MAXTEMP,maxtemp),(dt.RH,rh),(dt.MINRH,minrh),(dt.MAXRH,maxrh),(dt.WIND,wind),(dt.RAIN,rain),(dt.DEWPOINT,dewpoint),(dt.PRESSURE,pressure)):
      self.addValue(k,ts,v,False)
     got=True
    elif ts==today:
     self.addValue(dt.RAIN,ts,rain,False)
     got=True
   return got
  except:
   self.lastKnownError="Warning: Failed to get yesterday data summary"
   log.info(self.lastKnownError)
   return False
 def __gf(self, apiKey):
  s=self.settings
  try:
   d=self.openURL(self.apiForecastURL+"?geocode=%s,%s&language=en-US&units=m&format=json&apiKey=%s"%(s.location.latitude,s.location.longitude,str(apiKey)))
   if d is None:
    self.lastKnownError="Cannot get forecast data"
    log.error(self.lastKnownError)
    return False
   self.__pf(json.loads(d.read()))
   return True
  except Exception,e:
   self.lastKnownError="Error: Cannot get forecast data"
   log.error(self.lastKnownError)
   return False
 def __pf(self, data):
  dp=data.get("daypart",None)[0]
  ic=dp["iconCode"];rh=dp["relativeHumidity"];wind=dp["windSpeed"]
  ts=data["validTimeUtc"];tmin=data["temperatureMin"];tmax=data["temperatureMax"];qpf=data["qpf"]
  f=self.__f
  for i,t in enumerate(ts):
   mintemp=f(tmin[i]);maxtemp=f(tmax[i])
   minrh=f(rh[2*i]);maxrh=f(rh[2*i+1])
   wd=wind[2*i];wn=wind[2*i+1]
   wind=None
   if wd is not None and wn is not None:
    wind=(f(wd)+f(wn))/2.
    wind=wind/3.6
   condition=self.__cc(ic[2*i])
   for k,v in((dt.MINTEMP,mintemp),(dt.MAXTEMP,maxtemp),(dt.MINRH,minrh),(dt.MAXRH,maxrh),(dt.WIND,wind),(dt.QPF,qpf[i]),(dt.CONDITION,condition)):
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
   return value if value is None else float(value)
  except:
   return None

