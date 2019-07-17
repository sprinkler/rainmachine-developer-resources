# Copyright (c) 2018 Bobsplace Media Engineering
# All rights reserved.
# Author: Bob Paauwe <bpaauwe@bobsplace.com>
#
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

from datetime import datetime
import urllib2, json, time, ssl, socket, threading, math
from urllib import urlencode
import time as mod_time

class WeatherFlow(RMParser):
    parserName = "WeatherFlow Parser"
    parserDescription = "Parse data from a WeatherFlow Smart Weather Station"
    parserForecast = False # True if parser provides future forecast data
    parserHistorical = True # True if parser also provides historical data (only actual observed data)
    #parserInterval = 6 * 3600             # Your parser running interval in seconds, data will only be mixed in hourly intervals
    #parserInterval = 1800             # Your parser running interval in seconds, data will only be mixed in hourly intervals
    parserInterval = 300             # Your parser running interval in seconds, data will only be mixed in hourly intervals
    #parserDebug = False
    parserDebug = True
    parserEnabled = True
    parserData = []
    started = False

    # Users must supply the sensor serial numbers
    params = {
        "AirSerialNumber": None,
        "SkySerialNumber": None
    }
    defaultParams = {
        "AirSerialNumber": None,
        "SkySerialNumber": None
    }

    def __init__(self):
        RMParser.__init__(self)
        self.started = False

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
        for i, rawdata in enumerate(self.parserData, start=0):
            if 'report' in rawdata:
                self.addValue(RMParse.dataType.TEMPERATURE, rawdata['ts'], rawdata['report']['temperature'])
                self.addValue(RMParse.dataType.RH, rawdata['ts'], rawdata['report']['humdity'])
                self.addValue(RMParse.dataType.PRESSURE, rawdata['ts'], rawdata['report']['pressure'])
                self.addValue(RMParse.dataType.WIND, rawdata['ts'], rawdata['report']['wind'])
                self.addValue(RMParse.dataType.SOLARRADIATION, rawdata['ts'], rawdata['report']['srad'])
                self.addValue(RMParse.dataType.RAIN, rawdata['ts'], rawdata['report']['rain'])
                self.addValue(RMParse.dataType.DEWPOINT, rawdata['ts'], rawdata['report']['dewpoint'])
                self.addValue(RMParse.dataType.MAXTEMP, rawdata['ts'], rawdata['report']['max_temp'])
                self.addValue(RMParse.dataType.MINTEMP, rawdata['ts'], rawdata['report']['min_temp'])
                self.addValue(RMParse.dataType.MAXRH, rawdata['ts'], rawdata['report']['max_humid'])
                self.addValue(RMParse.dataType.MINRH, rawdata['ts'], rawdata['report']['min_humid'])

                log.debug("timestamp = %s" % datetime.fromtimestamp(rawdata['ts']))
                log.debug("temperature = %f" % rawdata['report']["temperature"])
                log.debug("humidity = %f" % rawdata['report']["humidity"])
                log.debug("pressure = %f" % rawdata['report']["pressure"])
                log.debug("wind speed = %f" % rawdata['report']["wind"])
                log.debug("solar radiation = %f" % rawdata['report']["srad"])
                log.debug("rain = %f" % rawdata['report']["rain"])
                log.debug("dewpoint = %f" % rawdata['report']["dewpoint"])
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
        prev_air_hour = 0
        prev_sky_hour = 0
        prev_air_day = 0
        prev_sky_day = 0
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

            now = datetime.datetime.now()

            # Check if this is a new day, if so 
            if day_of_year != now.timetuple().tm_yday:
                # clear counters
                air_count = 0
                sky_count = 0
                temp_total = 0
                humd_total = 0
                pres_total = 0
                dewp_total = 0
                self.report = {
                        'temperature': 0,
                        'humidity': 0,
                        'pressure': 0,
                        'dewpoint': 0,
                        'wind': 0,
                        'srad': 0,
                        'rain': 0,
                        'max_temp': 100,
                        'min_temp': -100,
                        'max_humid': 0,
                        'min_humid': 100
                        }

                day_of_year = now.timetuple().tm_yday
                self.parserData[1] = self.parserData[0]

            #print("type = %s s/n = %s" % (data["type"], data["serial_number"]))

            if (data["type"] == "obs_air") and (data["serial_number"] == self.params["AirSerialNumber"]):

                air_count += 1

                temp_total += data["obs"][0][2]
                self.report["temperature"] = float(temp_total) / float(air_count)

                humd_total += data["obs"][0][3]
                self.report["humidity"] = float(humd_total) / float(air_count)

                # report pressure in hpa so convert from mb to hpa
                pres_total += (data["obs"][0][1] / 10.0)
                self.report["pressure"] = float(pres_total) / float(air_count)

                # Calculate dewpoint
                b = (17.625 * data["obs"][0][2]) / (243.04 + data["obs"][0][2])
                rh = float(data["obs"][0][3]) / 100.0
                c = math.log(rh)
                dewpoint = (243.04 * (c + b)) / (17.625 - c - b)
                dewp_total += dewpoint
                self.report["dewpoint"] = dewp_total / air_count

                # Track Min/Max
                if (data["obs"][0][2] > self.report["max_temp"]):
                    self.report["max_temp"] = data["obs"][0][2]

                if (data["obs"][0][2] < self.report["min_temp"]):
                    self.report["min_temp"] = data["obs"][0][2]

                if (data["obs"][0][3] > self.report["max_humid"]):
                    self.report["max_humid"] = data["obs"][0][3]

                if (data["obs"][0][3] < self.report["min_humid"]):
                    self.report["min_humid"] = data["obs"][0][3]


            if (data["type"] == "obs_sky") and (data["serial_number"] == self.params["SkySerialNumber"]):
                sky_count += 1

                wind_total += data["obs"][0][5]
                self.report["wind"] = float(wind_total) / float(sky_count)

                srad_total += data["obs"][0][10]
                self.report["srad"] = float(srad_total) / float(sky_count)

                rain_total += data["obs"][0][3]
                self.report["rain"] = rain_total

            ts = mod_time.mktime(now.timetuple()) + now.microsend / 1e6
            parserData[0] = {
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
    while True:
        p.perform()
        time.sleep(120)
