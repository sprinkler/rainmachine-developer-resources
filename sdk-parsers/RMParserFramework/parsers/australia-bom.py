from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging
from RMUtilsFramework.rmTimeUtils import *
from xml.etree import ElementTree as elementTree   # Your parser needed libraries

class AustraliaBOM(RMParser):
    parserName = "Australia BoM"         # Your parser name
    parserDescription = " Commonwealth of Australia Bureau of Meteorology" # A description for this parser

    parserEnabled = True
    parserInterval = 3600                    # Your parser running interval in seconds
    parserForecast = True
    parserHistorical = True
    parserDebug = True                      # Don't show extra debug messages

    defaultParams = {"Forecast Area": "Terrey Hills"
                , "Observation Area": "Sydney - Observatory Hill"
                , "State" : "NSW" } 
    params = {"Forecast Area": "Terrey Hills"
                , "Observation Area": "Sydney - Observatory Hill"
                , "State" : "NSW" }         # Internal params that can be changed with API call /parser/{id}/params

    def isEnabledForLocation(self, timezone, lat, long):
        return AustraliaBOM.parserEnabled

    def __getForecastURLForState(self, state):
        URL = None
        if self.parserDebug:
            log.debug("Got a state of %s" % state)
        if state == "QLD":
            URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDQ11295.xml"
        elif state == "NSW":
            URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDN11060.xml"
        elif state == "NT":
            URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDD10207.xml"
        elif state == "SA":
            URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDS10044.xml"
        elif state == "TAS":
            URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDT16710.xml"
        elif state == "VIC":
            URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDV10753.xml"
        elif state == "WA":
            URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDW14199.xml"

        return URL

    def __getObservationURLForState(self, state):
        # AFAICT BOM only has observation data for NSW? maybe cause its the free version?
        if state == "NSW":
            return "ftp://ftp.bom.gov.au/anon/gen/fwo/IDN60920.xml"  

        return None
    
    # These are apparently manually entered at the source, so typos etc are possible
    def __getConditionFromWeather(self, weather):
        condition = None
        if weather == "Rain":
            condition = RMParser.conditionType.LightRain
        elif weather == "Showers":
            condition = RMParser.conditionType.RainShowers
        elif weather == "Smoke":
            condition = RMParser.conditionType.Smoke
        elif weather == "Fine":
            condition = RMParser.conditionType.Fair
        elif weather == "Fog":
            condition = RMParser.conditionType.Fog
        elif weather == "Haze":
            condition = RMParser.conditionType.Haze
        elif weather == "Recent precip.":
            condition = RMParser.conditionType.ShowersInVicinity
        elif weather == "Freezing rain":
            condition = RMParser.conditionType.FreezingRain
        elif weather == "Thunderstorm":
            condition = RMParser.conditionType.Thunderstorm
        elif weather == "Recent thunderstorm":
            condition = RMParser.conditionType.ThunderstormInVicinity
        else:
            log.error("Unknown weather type %s", condition)
            condition = None
    
    # These are classed as "hourly results" in the API
    # Incoming format documented here: http://reg.bom.gov.au/catalogue/Observations-XML.pdf
    def __getObservationData(self, state, observationArea):
        if self.parserDebug:
            log.debug("Getting observation data")
        URL = self.__getObservationURLForState(state)

        if URL == None:
            self.lastKnownError = "Error: Only NSW supported"
            return
        if self.parserDebug:
            log.debug("Got a URL of %s" % URL)

        data = self.openURL(URL)

        if data is None:
            if self.parserDebug:
                log.debug("Did not get data")
            self.lastKnownError = "Error: No data received from server"
            return

        if self.parserDebug:
            log.debug("Got data")

        foundObservationArea = False
        xmldata = elementTree.parse(data)
        for node in xmldata.getroot().getiterator(tag = "station"):
            if self.parserDebug:
                log.debug("Got a node of %s" % node.attrib['description'])
            if node.attrib['description'] != observationArea:
                continue
            foundObservationArea = True

            for subnode in node.getiterator(tag = "period"):
                subnodeDate = subnode.get("time-utc")
                subnodeDate = subnodeDate.rstrip('0:').rstrip('+') # python doesn't seem to like %z
                                                                    # but we know its UTC so we don't need it
                timestamp = rmTimestampFromDateAsString(subnodeDate, '%Y-%m-%dT%H:%M:%S')
                log.info("Observation time: %s" % subnodeDate)
                mintemp = None
                maxtemp = None
                temperature = None
                rh = None
                wind = None # m/s
                rain = 0.0
                rain_timestamp = None
                rain_24hr = 0.0
                rain_24hr_timestamp = None
                pressure = None # kpa
                dewpoint = None
                condition = None

                for element in subnode.getiterator(tag = "element"):
                    type = element.get("type")
                    if type == 'apparent_temp':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'delta_t':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'air_temperature':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        temperature = self.__toFloat(element.text)
                    elif type == 'dew_point':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        dewpoint = self.__toFloat(element.text)
                    elif type == 'pres':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        pressure = self.__toFloat(element.text) / 10 # convert hectaPa to kiloPa
                    elif type == 'msl_pres':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'qnh_pres':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'rain_hour':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'rain_ten':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'rel-humidity':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        rh = self.__toFloat(element.text)
                    elif type == 'weather':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        condition = self.__getConditionFromWeather(element.text)
                    elif type == 'wind_dir':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'wind_dir_deg':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'wind_spd_kmh':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        wind = self.__toFloat(element.text) / 3.6 # from km/h to m/s
                    elif type == 'wind_spd':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                    elif type == 'rainfall_24hr':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        rain_24hr = self.__toFloat(element.text)
                        elementDate = element.get("start-time-utc")
                        if not elementDate:
                            log.error("Failed to find element date: %s" % element)
                            rain_24hr_timestamp = timestamp
                        else:
                            elementDate = elementDate.rstrip('0:').rstrip('+') # python doesn't seem to like %z
                                                                               # but we know its UTC so we don't need it
                            rain_24hr_timestamp = rmTimestampFromDateAsString(elementDate, '%Y-%m-%dT%H:%M:%S')

                    elif type == 'rainfall':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        rain = self.__toFloat(element.text)
                        elementDate = element.get("start-time-utc")
                        if not elementDate:
                            log.error("Failed to find element date: %s" % element)
                            rain_timestamp = timestamp
                        else:
                            elementDate = elementDate.rstrip('0:').rstrip('+') # python doesn't seem to like %z
                                                                               # but we know its UTC so we don't need it
                            rain_timestamp = rmTimestampFromDateAsString(elementDate, '%Y-%m-%dT%H:%M:%S')
                    elif type == 'maximum_air_temperature':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        maxtemp = self.__toFloat(element.text)
                    elif type == 'minimum_air_temperature':
                        if parserDebug:
                            log.debug("Got %s for %s" % (element.text, type))
                        mintemp = self.__toFloat(element.text)
                    elif parserDebug:
                        log.debug("Got unknown type %s" % type)

                if parserDebug:
                    log.debug("Update temp: %s, rh: %s, Wind: %s, Rain: %s, Dewpoint: %s, Pressure: %s, min/max Temp: %s/%s " 
                        % ((temperature is None and '' or str(temperature))
                        , (rh is None and '' or str(rh))
                        , (wind is None and '' or str(wind))
                        , (rain is None and '' or str(rain))
                        , (dewpoint is None and '' or str(dewpoint))
                        , (pressure is None and '' or str(pressure))
                        , (mintemp is None and '' or str(mintemp))
                        , (maxtemp is None and '' or str(maxtemp))))
                
                self.addValue(RMParser.dataType.TEMPERATURE, timestamp, temperature)
                self.addValue(RMParser.dataType.MINTEMP, timestamp, mintemp)
                self.addValue(RMParser.dataType.MAXTEMP, timestamp, maxtemp)
                if rh:
                    self.addValue(RMParser.dataType.RH, timestamp, rh)
                if wind:
                    self.addValue(RMParser.dataType.WIND, timestamp, wind)
              #  if rain_timestamp:
              #      self.addValue(RMParser.dataType.RAIN, rain_timestamp, rain)
                if rain_24hr_timestamp:
                    self.addValue(RMParser.dataType.RAIN, rain_24hr_timestamp, rain_24hr)
                if dewpoint:
                    self.addValue(RMParser.dataType.DEWPOINT, timestamp, dewpoint)
                if pressure:
                    self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)
            if self.parserDebug:
                log.debug(self.result)
            break
        if foundObservationArea == False:
            self.lastKnownError = "Failed to find Observation Area"
            return
         

    def __getForecastData(self, state, forecastArea):
        if self.parserDebug:
            log.debug("Getting forecast data")

        URL = self.__getForecastURLForState(state)
         
        if URL == None:
            self.lastKnownError = "Error: Invalid state, must be QLD, NSW, NT, SA, TAS, VIC or WA"
            return

        if self.parserDebug:
            log.debug("Got a URL of %s" % URL)

        data = self.openURL(URL)

        if data is None:
            if self.parserDebug:
                log.debug("Did not get data")
            self.lastKnownError = "Error: No data received from server"
            return

        if self.parserDebug:
            log.debug("Got data")

        foundForecastArea = False
        xmldata = elementTree.parse(data)

        if self.parserDebug:
            log.debug("Parsing XML looking for 'area'")
        for node in xmldata.getroot().getiterator(tag = "area"):
            if self.parserDebug:
                log.debug("Got a node of %s" % node.attrib['description'])
            if node.attrib['description'] != forecastArea:
                continue
            foundForecastArea = True

            if self.parserDebug:
                log.debug("Matched on %s" % forecastArea)

            for subnode in node.getiterator(tag = "forecast-period"):
                subnodeDate = subnode.get("start-time-utc")
                subnodeTimestamp = rmTimestampFromDateAsString(subnodeDate, '%Y-%m-%dT%H:%M:%SZ')
                log.info("forecast-period time - %s" % subnodeDate)
                for element in subnode.getiterator(tag = "element"):
                    mint = None
                    maxt = None
                    qpfMin = None
                    qpfMax = None
                    qpfAvg = None
                    pop = None

                    type = element.get("type")
                    if type == "air_temperature_minimum":
                        try:
                            mint = self.__toFloat(element.text)
                            log.info("\tMin Temp: %s" % mint)
                            self.addValue(RMParser.dataType.MINTEMP, subnodeTimestamp, mint)
                        except:
                            log.error("Cannot get minimum temperature")
                    elif type == "air_temperature_maximum":
                        try:
                            maxt = self.__toFloat(element.text)
                            self.addValue(RMParser.dataType.MAXTEMP, subnodeTimestamp, maxt)
                            log.info("\tMax Temp: %s" % maxt)
                        except:
                            log.error("Cannot get max temperature")
                    elif type == "precipitation_range":
                        try:
                            qpfMin, _, qpfMax, _ = element.text.split() # will result in ['15', 'to', '35', 'mm']
                            qpfAvg = (self.__toFloat(qpfMin) + self.__toFloat(qpfMax))/2
                            log.info("\tQPF Avg: %s" % qpfAvg)
                            self.addValue(RMParser.dataType.QPF, subnodeTimestamp, qpfAvg)
                        except:
                            log.error("Cannot get precipitation forecast")
                    elif type == "probability_of_precipitation":
                        try:
                            pop =  self.__toInt(element.text.rstrip('%'))
                            log.info("\POP: %s" % qpfAvg)
                            self.addvalue(RMParser.dataType.POP, subnodeTimestamp, pop)
                        except:
                            log.error("Cannot get probability_of_precipitation forecast")
                    
                if self.parserDebug:
                    # Sometimes we get a forecast result in the past, however addValue will not add a historical value, so we might get
                    # no record
                    if subnodeTimestamp in self.result:
                        log.debug("Forcast: %s / %s : %s" % (str(subnodeTimestamp), subnodeDate, self.result[subnodeTimestamp]))
                    else:
                        log.debug("Forcast: %s / %s not found" % (str(subnodeTimestamp), subnodeDate))
            break
        if foundForecastArea == False:
            self.lastKnownError = "Failed to find Forecast Area"
            return

    # The function that will be executed must have this name
    def perform(self):
        # downloading data from a URL convenience function since other python libraries can be used
        # Each xml file contains a small subset of locations, need to figure out the right location
        # http://reg.bom.gov.au/other/Ftp.shtml 
        self.__getForecastData( self.params["State"], self.params["Forecast Area"])

        self.__getObservationData( self.params["State"], self.params["Observation Area"])

        if parserDebug:
            log.debug("Parsing done")
            if self.parserDebug:
                for time_period in self.result:
                    log.debug("%s : %s" % (str(time_period), self.result[time_period]))
       

    def __toFloat(self, value):
        if value is None:
            return value
        return float(value)
    def __toInt(self, value):
        if value is None:
            return value
        return int(value)

if __name__  == '__main__':
    p = AustraliaBOM()
    p.perform()