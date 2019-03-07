import urllib
# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>
#   Meteobridge parser:
#          Gordon Larsen    <gordon@the-larsens.ca>


from RMParserFramework.rmParser import RMParser
#from RMUtilsFramework.rmUtils import distanceBetweenGeographicCoordinatesAsKm
from RMUtilsFramework.rmLogging import log
#from RMUtilsFramework.rmUtils import convertKnotsToMS
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp

#class PWSMeteobridge(RMParser):
class Meteobridge_parser():
    parserName = "Meteobridge PWS Parser"
    parserDescription = "Personal Weather Station direct data upload from Meteobridge"
    parserForecast = False
    parserHistorical = True
    parserEnabled = True
    parserDebug = True
    parserInterval = 1 * 60
    params = {"top_level_url" : "http://meteobridge.internal.home",
              "username" : "meteobridge",
              "password" : "meteobridge"
              }

def isEnabledForLocation(self, timezone, lat, long):
    return Meteobridge_parser.parserEnabled
  
# create a password manager
password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
username = 'meteobridge'
#password = 'meteobridge'

# Add the username and password.
# If we knew the realm, we could use it instead of None.
top_level_url = "http://meteobridge.internal.home"
password_mgr.add_password(None, top_level_url, username, password)

handler = urllib.request.HTTPBasicAuthHandler(password_mgr)

# create "opener" (OpenerDirector instance)
opener = urllib.request.build_opener(handler)

# use the opener to fetch a URL
opener.open(top_level_url)

# Install the opener.


# Now all calls to urllib.request.urlopen use our opener.
urllib.request.install_opener(opener)

def perform(self):

    urlPath = top_level_url + "/cgi-bin/template.cgi?template="
    values = "[th0temp-act]%20[th0hum-act]%20[thb0press-act]%20[sol0evo-act]%20[mbsystem-latitude]%20[mbsystem-longitude]%20[th0temp-dmax]%20[th0temp-dmin]%20[th0hum-dmax]%20[th0hum-dmin]%20[wind0avgwind-act]%20[sol0rad-act]%20[rain0total-act]%20[th0dew-act]&contenttype=text/plain;charset=iso-8859-1"
    headers = {''}

    req = urllib.request.Request(urlPath + values)
    with urllib.request.urlopen(req) as response:
        pwsContent = response.read()
    if pwsContent is None:
        return
    print (pwsContent)

    pwsContent = str(pwsContent)
    print (pwsContent)
    pwsContent = pwsContent.strip('b')
    pwsContent = pwsContent.strip("'")
    pwsArray = pwsContent.split(" ")
    print (pwsArray)

    lat = float(pwsArray[4])
    long = float(pwsArray[5])

    temperature = float(pwsArray[4])
    et0 = float(pwsArray[3])
    mintemp = float(pwsArray[7])
    maxtemp = float(pwsArray[6])
    rh = float(pwsArray[1])
    minrh = float(pwsArray[9])
    maxrh = float(pwsArray[8])
    wind = float(pwsArray[10])
    solarradiation = float(pwsArray[11])  # needs to be converted from watt/sqm*h to Joule/sqm

    if solarradiation is not None:
                solarradiation *= 0.0864

    rain = float(pwsArray[12])
    dewpoint = float(pwsArray[13])
    pressure = float(pwsArray[2]) / 10
    #conditionIcon = self.conditionConvert(self.__toFloat(pwsArray[48]))

    print(self.result)
    return

def __toFloat(self, value):
        if value is None:
            return value
        return float(value)

if __name__ == "__main__":
    p = Meteobridge_parser()
    p.perform()
#aa=perform('self')
