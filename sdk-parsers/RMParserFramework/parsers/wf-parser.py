# Copyright (c) 2018 Bobsplace Media Engineering
# All rights reserved.
# Author: Bob Paauwe <bpaauwe@bobsplace.com>
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

# WeatherFlow Smart Weather Station data parser.
#
# Run a thread in the background that listens for the WeatherFlow hub data
# broadcasts and collect the relevant data. The hub does a UDP broadcast
# for each sensor.  The body of the broadcast contains JSON formatted data
# from the sensor.
#
# Each sensor has a unique serial number. Multiple sensors are allowed and
# this parser must be configured with the specific sensors to track. Only
# one Air and one Sky may be tracked.

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmGetStartOfDay

from datetime import datetime
import urllib2, json, time, ssl, socket, threading, math
from urllib import urlencode
import time as mod_time

class WeatherFlow(RMParser):
    parserName = "WeatherFlow Personal Weather Station"
    parserDescription = "Retrieves data from a WeatherFlow Smart Weather Station on local network"
    parserForecast = False 
    parserHistorical = True
    parserInterval = 600
    #parserDebug = False
    parserDebug = True
    parserEnabled = True
    parserData = []
    started = False
    newDay = 0

    # Users must supply the sensor serial numbers
    params = {
        "AirSerialNumber" : "AR-00000000",
        "SkySerialNumber" : "SK-00000000",          
        "TempestSerialNum": "ST-00000000"           
    }
    defaultParams = {
        "AirSerialNumber" : "AR-00000000",
        "SkySerialNumber" : "SK-00000000",
        "TempestSerialNum": "ST-00000000"
    }

    parserData = [dict() for x in range(2)]

    def __init__(self):
        RMParser.__init__(self)
        self.started = False
        log.info("Initializing WeatherFlow local UDP parser (ver 1.2.0)")

    def perform(self):                # The function that will be executed must have this name

        # Based on a number of discussions, the following is what should
        # be sent here.
        #
        # if new day:
        #    send last data point for temperaturer of previous day
        #    send last data point for humidity of previous day
        #    send last data point for pressure of previous day
        #    send last data point for wind of previous day
        #    send last data point for solar rad of previous day
        #    send last data point for dewpoint of previous day
        #    send last data point for rain of previous day
        #    send min/max temperature and humidity for previous day
        #    delete entries indexed at this timestamp
        # send average temperature for today
        # send average humidity for today
        # send average pressure for today
        # send average wind for today
        # send average solar rad for today
        # send total rain for today
        # send min/max temperature for today
        # send min/max humidity for today
        #
        # need to store data for only one time each day (11:59pm), maybe
        # use a dictionary structure like:
        #
        #  {'timestamp': 333333333, 'readings': {
        #       'temperature': <temp>,
        #       'humidity': <humidity>,
        #       }
        #  }
        #   
        if self.started == False:
            self.started = True
            log.debug("Starting UPD Listener thread.")
            # TODO: How do we stop the thread once it's started?
            threading.Thread(target = self.wfUDPData).start()
            return  None # First time, just start the thread, we have no data yet.

            
        for idx, rawdata in enumerate(self.parserData):
            if 'report' in rawdata:
                logMsg = "Interval Summary:"
                if idx == 1:               # if looking at yesterday data (0 = today, 1 = yesterday) ...
                    if self.newDay :       # Check if need to send yesterday's data
                        self.newDay = 0    # reset the flag and send yesterday's data   
                        logMsg = "Yesterday's EoD Summary:" 
                    else:                  # otherwise skip sending it, only want to send one time 
                        continue

                self.addValue(RMParser.dataType.TEMPERATURE, rawdata['ts'], rawdata['report']['temperature'])
                self.addValue(RMParser.dataType.RH, rawdata['ts'], rawdata['report']['humidity'])
                self.addValue(RMParser.dataType.PRESSURE, rawdata['ts'], rawdata['report']['pressure'])
                self.addValue(RMParser.dataType.WIND, rawdata['ts'], rawdata['report']['wind'])
                self.addValue(RMParser.dataType.SOLARRADIATION, rawdata['ts'], rawdata['report']['srad'])
                self.addValue(RMParser.dataType.RAIN, rawdata['ts'], rawdata['report']['rain'])
                self.addValue(RMParser.dataType.DEWPOINT, rawdata['ts'], rawdata['report']['dewpoint'])
                if rawdata['report']['max_temp'] < 60:
                    self.addValue(RMParser.dataType.MAXTEMP, rawdata['ts'], rawdata['report']['max_temp'])
                if rawdata['report']['max_temp'] > -60:
                    self.addValue(RMParser.dataType.MINTEMP, rawdata['ts'], rawdata['report']['min_temp'])
                self.addValue(RMParser.dataType.MAXRH, rawdata['ts'], rawdata['report']['max_humid'])
                self.addValue(RMParser.dataType.MINRH, rawdata['ts'], rawdata['report']['min_humid'])

                
                              
                log.info("%s temp(C,F): %.2f / %.2f, wind(m/s,mph): %.2f / %.2f, rain_dayTot(mm,in): %.2f / %.2f" % (logMsg, 
                        rawdata['report']["temperature"], ((rawdata['report']["temperature"] * 9 / 5) + 32), 
                        rawdata['report']["wind"], (rawdata['report']["wind"] * 2.237), 
                        rawdata['report']["rain"], (rawdata['report']["rain"] / 25.4) ))

                log.debug("timestamp = %s" % datetime.fromtimestamp(rawdata['ts']))
                log.debug("temperature = %f" % rawdata['report']["temperature"])
                log.debug("humidity = %f" % rawdata['report']["humidity"])
                log.debug("pressure = %f" % rawdata['report']["pressure"])
                log.debug("wind speed = %f" % rawdata['report']["wind"])
                log.debug("solar radiation = %f" % rawdata['report']["srad"])
                log.debug("rain = %f" % rawdata['report']["rain"])
                log.debug("dewpoint = %f" % rawdata['report']["dewpoint"])
                log.debug("max temperature = %f" % rawdata['report']["max_temp"])
                log.debug("min temperature = %f" % rawdata['report']["min_temp"])
                log.debug("max humidity = %f" % rawdata['report']["max_humid"])
                log.debug("min humidity = %f" % rawdata['report']["min_humid"])
                log.debug("")

               

    # Listen for and process WeatherFlow data that is broadcast on UDP port 50222
    def wfUDPData(self):
        air_count = 0
        sky_count = 0
        temp_total = 0
        humd_total = 0
        pres_total = 0
        wind_total = 0
        srad_total = 0
        rain_total = 0
        dewp_total = 0
        bufferSize = 1024 # whatever you need
        port = 50222
        day_of_year = 0

        log.debug("Start listening on port %d" % port)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', port))
        except:
            log.Error("Socket failure")

        log.debug("Start recieve loop")
        while self.started:
            hub = s.recvfrom(bufferSize)
            data = json.loads(hub[0]) # hub is a truple (json, ip, port)

            now = datetime.now()

            # Check if this is a new day, if so 
            if day_of_year != now.timetuple().tm_yday:
                # clear counters
                air_count = 0
                sky_count = 0
                temp_total = 0
                humd_total = 0
                pres_total = 0
                wind_total = 0
                srad_total = 0
                rain_total = 0
                dewp_total = 0
                self.report = {
                        'temperature': 0,
                        'humidity': 0,
                        'pressure': 0,
                        'dewpoint': 0,
                        'wind': 0,
                        'srad': 0,
                        'rain': 0,
                        'max_temp': -100,
                        'min_temp': 100,
                        'max_humid': 0,
                        'min_humid': 100
                        }

                day_of_year = now.timetuple().tm_yday
                self.parserData[1] = self.parserData[0]
 
                self.newDay +=1            # signal that just rolled into a new day, need to send a yesterday summary onetime

                # reset yesterday's timestamp to start of day
                if 'ts' in self.parserData[1]:
                    self.parserData[1]['ts'] = rmGetStartOfDay(self.parserData[1]['ts'])

            #log.debug("type = %s broadcast s/n = %s  TEMPEST target: %s" % (data["type"], data["serial_number"], self.params["TempestSerialNum"]))

            debugMsg = "Observation: "

            if  (   ((data["type"] == "obs_air") and (data["serial_number"] == self.params["AirSerialNumber"])) or
                    ((data["type"] == "obs_st") and (data["serial_number"] == self.params["TempestSerialNum"])) ):

                if   data["type"] == "obs_air":                  
                    pres_idx = 1                # UDP packet data indexes for Air device
                    temp_idx = 2
                    humd_idx = 3
                else:
                    pres_idx = 6                # UDP packet data indexes for TEMPEST device
                    temp_idx = 7
                    humd_idx = 8

                air_count += 1

                temp_total += data["obs"][0][temp_idx]
                self.report["temperature"] = float(temp_total) / float(air_count)

                humd_total += data["obs"][0][humd_idx]
                self.report["humidity"] = float(humd_total) / float(air_count)

                # report pressure in hpa so convert from mb to hpa
                pres_total += (data["obs"][0][pres_idx] / 10.0)
                self.report["pressure"] = float(pres_total) / float(air_count)

                # Calculate dewpoint
                b = (17.625 * data["obs"][0][temp_idx]) / (243.04 + data["obs"][0][temp_idx])
                rh = float(data["obs"][0][humd_idx]) / 100.0
                c = math.log(rh)
                dewpoint = (243.04 * (c + b)) / (17.625 - c - b)
                dewp_total += dewpoint
                self.report["dewpoint"] = dewp_total / air_count

                # Track Min/Max
                if (data["obs"][0][temp_idx] > self.report["max_temp"]):
                    self.report["max_temp"] = data["obs"][0][temp_idx]

                if (data["obs"][0][temp_idx] < self.report["min_temp"]):
                    self.report["min_temp"] = data["obs"][0][temp_idx]

                if (data["obs"][0][humd_idx] > self.report["max_humid"]):
                    self.report["max_humid"] = data["obs"][0][humd_idx]

                if (data["obs"][0][humd_idx] < self.report["min_humid"]):
                    self.report["min_humid"] = data["obs"][0][humd_idx]

                
                debugMsg += "Temp (dF)= %.2f, " % ((float(data["obs"][0][temp_idx]) * 9 / 5) + 32)    # convert degC to degF
                debugMsg += "Humid  = %.2f, " % data["obs"][0][humd_idx]
                debugMsg += "Press (inHg) = %.2f, " % (float(data["obs"][0][pres_idx]) /  33.8639 )

        
            if  (   ((data["type"] == "obs_sky") and (data["serial_number"] == self.params["SkySerialNumber"])) or
                    ((data["type"] == "obs_st") and (data["serial_number"] == self.params["TempestSerialNum"])) ):

                if   data["type"] == "obs_sky":                  
                    wind_idx = 5                # UDP  Packet data indexes for Sky device
                    srad_idx = 10
                    rain_idx = 11
                else:
                    wind_idx = 2                # UDP packet data indexes for TEMPEST device
                    srad_idx = 11
                    rain_idx = 12


                sky_count += 1

                wind_total += data["obs"][0][wind_idx]
                self.report["wind"] = float(wind_total) / float(sky_count)

                srad_total += data["obs"][0][srad_idx]
                self.report["srad"] = float(srad_total) / float(sky_count)

                rain_total += data["obs"][0][rain_idx]
                self.report["rain"] = rain_total


                debugMsg += "Cumulative Rain (inch) = %.2f" % (rain_total / 25.4)
                log.debug(debugMsg)
           
 
            ts = mod_time.mktime(now.timetuple()) + now.microsecond / 1e6
            self.parserData[0] = {
                    'ts': ts,
                    'report':self.report
                    }

        log.debug("Receive thread exiting")
        s.close()
        self.started = False


# To run in pycharm uncomment the following lines
if __name__ == "__main__":
    p = WeatherFlow()
    p.params["AirSerialNumber"] = "AR-00000000"
    p.params["SkySerialNumber"] = "SK-00000000"
    p.params["TempestSerialNum"] = "ST-00000000"
    while True:
        p.perform()
        time.sleep(120)
