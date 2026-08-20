# RainMachine service audit - run ON the controller with the stock python.
#   python rm-service-audit.py
#
# For every host the built-in parsers talk to, this reports whether the
# device's own stack can reach it (urllib2) and whether the ctypes/libssl
# SNI path can. Two failures look identical in the parser logs but need
# completely different fixes:
#
#   urllib2 fails, ctypes works  -> TLS SNI problem, fixable in the parser
#   both fail with the same code -> the service changed, parser needs updating
#   DNS failure                  -> the host is gone
#
# Python 2.6/2.7 only. Nothing is written and no API keys are used; several
# endpoints will answer 400/401/403 without credentials, which still proves
# the host is reachable and answering.


import ctypes
import os
import socket
import ssl
import struct
import sys
import time
import urllib2


SSL_CTRL_SET_TLSEXT_HOSTNAME = 55
TLSEXT_NAMETYPE_host_name = 0
SSL_RETRY = (2, 3, 5)


SSL_LIBS = ["/usr/lib/libssl.so.1.0.0", "/lib/libssl.so.1.0.0",
            "/usr/lib/libssl.so.1.0.2", "/usr/lib/libssl.so.1.1",
            "/usr/lib/libssl.so", "/system/lib/libssl.so",
            "/system/lib64/libssl.so", "libssl.so.1.0.0", "libssl.so"]
CRYPTO_LIBS = [p.replace("libssl", "libcrypto") for p in SSL_LIBS]


# (parser, url, note)  - paths chosen to be harmless GETs
TARGETS = [
    ("noaa",        "https://noaa.rainmachine.com/xml/sample_products/browser_interface/ndfdXMLclient.php?lat=37.6&lon=-121.8&product=time-series&begin=2026-01-01&Unit=e&temp=temp", "RainMachine proxy, sends Host: graphical.weather.gov"),
    ("noaa",        "https://forecast.rainmachine.com/xml/sample_products/browser_interface/ndfdXMLclient.php?token=px808345forc&lat=37.6&lon=-121.8&product=time-series&begin=2026-01-01&Unit=e&temp=temp", "RainMachine proxy #2"),
    ("noaa",        "https://graphical.weather.gov/xml/sample_products/browser_interface/ndfdXMLclient.php?lat=37.6&lon=-121.8&product=time-series&begin=2026-01-01&Unit=e&temp=temp", "NWS NDFD legacy XML, last fallback"),
    ("noaa (new)",  "https://api.weather.gov/points/37.6,-121.8", "not used by the parser - the modern replacement"),
    ("netatmo",     "https://api.netatmo.com/oauth2/token", "expect 400/405 without a body - proves reachability. If the built-in parser cannot complete TLS, check what it actually calls: strings /rainmachine-app/RMParserFramework/parsers/netatmo-parser.pyc | grep -iE 'http|grant_type|oauth'"),
    ("owm",         "https://api.openweathermap.org/data/2.5/forecast?lat=37.6&lon=-121.8", "expect 401 without appid"),
    ("forecast-io", "https://api.darksky.net/forecast/0/37.6,-121.8", "Dark Sky"),
    ("met-no",      "https://api.met.no/weatherapi/locationforecast/2.0/classic?lat=37.6&lon=-121.8", "check UA policy"),
    ("cimis",       "http://et.water.ca.gov/api/data", "plain HTTP in the parser"),
    ("fawn",        "http://fawn.ifas.ufl.edu/controller.php/lastHour/summary/json", "plain HTTP in the parser"),
    ("wunderground","https://api.weather.com/v2/pws/dailysummary/7day?stationId=X&format=json&units=m&apiKey=X", "known 421 without SNI - the control case"),
]


AGENT = "RainMachine v2"
TIMEOUT = 20




class Ssl(object):
    inst = None
    dead = False


    @classmethod
    def get(cls):
        if cls.dead:
            return None
        if cls.inst is None:
            try:
                cls.inst = Ssl()
            except Exception, e:
                cls.dead = True
                print "  libssl unavailable: %s" % e
                return None
        return cls.inst


    def __init__(self):
        self.crypto, _ = self.load(CRYPTO_LIBS, True)
        self.lib, self.path = self.load(SSL_LIBS, False)
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


    def load(self, names, glob):
        err = None
        for n in names:
            if n.startswith("/") and not os.path.exists(n):
                continue
            try:
                if glob:
                    return ctypes.CDLL(n, mode=ctypes.RTLD_GLOBAL), n
                return ctypes.CDLL(n), n
            except Exception, e:
                err = e
        raise Exception(str(err))




def sniGet(url):
    b = Ssl.get()
    if b is None:
        return "no libssl"
    rest = url.split("://", 1)[1]
    cut = rest.find("/")
    host = rest[:cut] if cut >= 0 else rest
    path = rest[cut:] if cut >= 0 else "/"
    try:
        sock = socket.create_connection((host, 443), TIMEOUT)
    except Exception, e:
        return "conn %s" % (str(e)[:28])
    sock.setblocking(1)
    try:
        tv = struct.pack("ll", TIMEOUT, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, tv)
    except Exception:
        pass
    s = b.lib
    ctx = con = None
    try:
        ctx = s.SSL_CTX_new(b.method())
        con = s.SSL_new(ctx)
        s.SSL_set_fd(con, sock.fileno())
        if s.SSL_ctrl(con, SSL_CTRL_SET_TLSEXT_HOSTNAME, TLSEXT_NAMETYPE_host_name, host) != 1:
            return "SNI set failed"
        if s.SSL_connect(con) != 1:
            return "handshake failed"
        req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\n"
               "Accept: */*\r\nConnection: close\r\n\r\n" % (path, host, AGENT))
        sent = 0
        while sent < len(req):
            n = s.SSL_write(con, req[sent:], len(req) - sent)
            if n <= 0:
                return "write failed"
            sent += n
        buf = ctypes.create_string_buffer(2048)
        deadline = time.time() + TIMEOUT
        data = ""
        while len(data) < 40:
            n = s.SSL_read(con, buf, 2048)
            if n > 0:
                data += buf.raw[:n]
                continue
            if s.SSL_get_error(con, n) in SSL_RETRY and time.time() < deadline:
                time.sleep(0.1)
                continue
            break
        if not data:
            return "empty reply"
        return data.split("\r\n")[0].replace("HTTP/1.1 ", "").replace("HTTP/1.0 ", "")[:34]
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




def viaUrllib(url):
    req = urllib2.Request(url, headers={"User-Agent": AGENT, "Accept": "*/*"})
    try:
        r = urllib2.urlopen(req, timeout=TIMEOUT)
        return "%s OK" % r.getcode()
    except urllib2.HTTPError, e:
        return "%s %s" % (e.code, str(e.reason)[:22])
    except Exception, e:
        return str(e)[:34]




def main():
    b = Ssl.get()
    print "python  : %s" % sys.version.split()[0]
    print "HAS_SNI : %s   SSLContext: %s" % (getattr(ssl, "HAS_SNI", False),
                                             hasattr(ssl, "SSLContext"))
    print "libssl  : %s" % (b.path if b else "not loaded")
    print
    print "%-13s %-30s %-26s %s" % ("PARSER", "HOST", "urllib2 (device stack)", "ctypes+SNI")
    print "-" * 104
    for parser, url, note in TARGETS:
        host = url.split("://", 1)[1].split("/")[0]
        u = viaUrllib(url)
        c = sniGet(url) if url.startswith("https") else "n/a (http)"
        print "%-13s %-30s %-26s %s" % (parser, host, u[:26], c)
    print
    print "Read as: urllib2 fails + ctypes works = SNI problem, fixable in the parser."
    print "         both fail the same way        = the service changed."
    print "         name resolution error         = the host is gone."




if __name__ == "__main__":
    main()