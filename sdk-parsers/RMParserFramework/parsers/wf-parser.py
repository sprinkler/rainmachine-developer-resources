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

import urllib2, json, time, ssl, socket, threading, math
from urllib import urlencode

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
    hourlyData = {}
    maxData = {}
    minData = {}
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

        if self.started == False:
            self.started = True
            log.debug("Starting UPD Listener thread.")
            # TODO: How do we stop the thread once it's started?
            threading.Thread(target = self.wfUDPData).start()
            return  None # First time, just start the thread, we have no data yet.

        ts = int(time.time())

        if "Temperature" in self.hourlyData:
            self.addValue(RMParser.dataType.TEMPERATURE, ts, self.hourlyData["Temperature"])
            log.debug("temperature = %f" % self.hourlyData["Temperature"])
        if "Humidity" in self.hourlyData:
            self.addValue(RMParser.dataType.RH, ts, self.hourlyData["Humidity"])
            log.debug("humidity = %f" % self.hourlyData["Humidity"])
        if "Pressure" in self.hourlyData:
            self.addValue(RMParser.dataType.PRESSURE, ts, self.hourlyData["Pressure"])
            log.debug("pressure = %f" % self.hourlyData["Pressure"])
        if "Wind" in self.hourlyData:
            self.addValue(RMParser.dataType.WIND, ts, self.hourlyData["Wind"])
            log.debug("wind speed = %f" % self.hourlyData["Wind"])
        if "SolarRadiation" in self.hourlyData:
            self.addValue(RMParser.dataType.SOLARRADIATION, ts, self.hourlyData["SolarRadiation"])
            log.debug("solar radiation = %f" % self.hourlyData["SolarRadiation"])
        if "Rain" in self.hourlyData:
            self.addValue(RMParser.dataType.RAIN, ts, self.hourlyData["Rain"])
            log.debug("rain = %f" % self.hourlyData["Rain"])
        if "Dewpoint" in self.hourlyData:
            self.addValue(RMParser.dataType.DEWPOINT, ts, self.hourlyData["Dewpoint"])
            log.debug("dewpoint = %f" % self.hourlyData["Dewpoint"])

        if "Temperature" in self.maxData:
            self.addValue(RMParser.dataType.MAXTEMP, ts, self.maxData["Temperature"])
        if "Temperature" in self.minData:
            self.addValue(RMParser.dataType.MINTEMP, ts, self.minData["Temperature"])
        if "Humidity" in self.maxData:
            self.addValue(RMParser.dataType.MAXRH, ts, self.maxData["Humidity"])
        if "Humidity" in self.minData:
            self.addValue(RMParser.dataType.MINRH, ts, self.minData["Humidity"])


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

            #print("type = %s s/n = %s" % (data["type"], data["serial_number"]))

            if (data["type"] == "obs_air") and (data["serial_number"] == self.params["AirSerialNumber"]):
                ts = data["obs"][0][0]
                if int(ts / 3600) != prev_air_hour:
                    air_count = 0
                    temp_total = 0
                    humd_total = 0
                    pres_total = 0
                    dewp_total = 0

                if int(ts / (3600 * 24)) != prev_air_day:
                    log.debug("New Day! %d vs %d" % ((ts / (3600 * 24)), prev_air_day))
                    self.maxData["Temperature"] = -100
                    self.minData["Temperature"] = 100
                    self.maxData["Humidity"] = 0
                    self.minData["Humidity"] = 100

                prev_air_day = int(ts / (3600 * 24))
                prev_air_hour = int(ts / 3600)
                air_count += 1

                temp_total += data["obs"][0][2]
                self.hourlyData["Temperature"] = float(temp_total) / float(air_count)

                humd_total += data["obs"][0][3]
                self.hourlyData["Humidity"] = float(humd_total) / float(air_count)

                # report pressure in hpa so convert from mb to hpa
                pres_total += (data["obs"][0][1] / 10.0)
                self.hourlyData["Pressure"] = float(pres_total) / float(air_count)

                # Calculate dewpoint
                b = (17.625 * data["obs"][0][2]) / (243.04 + data["obs"][0][2])
                rh = float(data["obs"][0][3]) / 100.0
                c = math.log(rh)
                dewpoint = (243.04 * (c + b)) / (17.625 - c - b)
                dewp_total += dewpoint
                self.hourlyData["Dewpoint"] = dewp_total / air_count

                # Track Min/Max
                if (data["obs"][0][2] > self.maxData["Temperature"]):
                    self.maxData["Temperature"] = data["obs"][0][2]

                if (data["obs"][0][2] < self.minData["Temperature"]):
                    self.minData["Temperature"] = data["obs"][0][2]

                if (data["obs"][0][3] > self.maxData["Humidity"]):
                    self.maxData["Humidity"] = data["obs"][0][3]

                if (data["obs"][0][3] < self.minData["Humidity"]):
                    self.minData["Humidity"] = data["obs"][0][3]

            if (data["type"] == "obs_sky") and (data["serial_number"] == self.params["SkySerialNumber"]):
                ts = data["obs"][0][0]
                if int(ts / 3600) != prev_sky_hour:
                    sky_count = 0
                    wind_total = 0
                    srad_total = 0

                if int(ts / (3600 * 24)) != prev_sky_day:
                    log.debug("New Day! %d vs %d" % ((ts / (3600 * 24)), prev_sky_day))
                    rain_total = 0


                prev_sky_hour = int(ts / 3600)
                prev_sky_day = int(ts / (3600 * 24))
                sky_count += 1

                wind_total += data["obs"][0][5]
                self.hourlyData["Wind"] = float(wind_total) / float(sky_count)

                srad_total += data["obs"][0][10]
                self.hourlyData["SolarRadiation"] = float(srad_total) / float(sky_count)

                rain_total += data["obs"][0][3]
                self.hourlyData["Rain"] = rain_total

        log.debug("Receive thread exiting")
        s.close()
        self.started = False


# To run in pycharm uncomment the following lines
if __name__ == "__main__":
    p = WeatherFlow()
    p.params["AirSerialNumber"] = "ACUAIR-2058"
    p.params["SkySerialNumber"] = "ACUSKY-2058"
    while True:
        p.perform()
        time.sleep(120)
