#RainMachine REST API JavaScript implementation

This is a implementation of RainMachine REST API in javascript. RainMachine REST API documentation is available here: http://docs.rainmachine.apiary.io/
This implementation is used on https://github.com/sprinkler/rainmachine-web-ui.

A simple example usage can be found on index.html, which uses apiary.io mock server. If you wish to run directly on a RainMachine device edit ``js/rainmachine-api-v4.js``
and modify **host** and **port** variables to point to your desired RainMachine (either local ip or remote access through my.rainmachine.com).

#Available functions
You can use the functions below by either synchronous method: APISync.getApiVer() or aynchronously: APIAsync.getApiVer().then()

- getApiVer = function()

http://docs.rainmachine.apiary.io/#reference/api-versions

- auth = function(password, remember)
- authChange = function(oldPass, newPass)

http://docs.rainmachine.apiary.io/#reference/authentication
- getProvision = function()
- getProvisionWifi = function()
- getProvisionCloud = function()
- setProvision = function(systemObj, locationObj)
- setProvisionName = function(name)
- setProvisionCloud = function(cloudObj)
- setProvisionCloudEmail = function(email)
- setProvisionCloudEnable = function(isEnabled)
- setProvisionCloudReset = function()
- setProvisionReset = function(withRestart)

http://docs.rainmachine.apiary.io/#reference/provision 

- getDailyStats = function(dayDate, withDetails)

http://docs.rainmachine.apiary.io/#reference/daily-stats
- getRestrictionsRainDelay = function()
- getRestrictionsGlobal = function()
- getRestrictionsHourly = function()
- getRestrictionsCurrently = function()
- setRestrictionsRainDelay = function(days)
- setRestrictionsGlobal = function(globalRestrictionObj)
- setRestrictionsHourly = function(hourlyRestrictionObj)
- deleteRestrictionsHourly = function(id)

http://docs.rainmachine.apiary.io/#reference/restrictions

- getPrograms = function(id)
- getProgramsNextRun = function()
- setProgram = function(id, programProperties)
- newProgram = function(programProperties)
- deleteProgram = function(id)
- startProgram = function(id)
- stopProgram = function(id)

http://docs.rainmachine.apiary.io/#reference/programs 

- getZones = function(id)
- startZone = function(id, duration)
- stopZone = function(id)
- getZonesProperties = function(id)
- setZonesProperties = function(id, properties, advancedProperties)

http://docs.rainmachine.apiary.io/#reference/zones
- getWateringLog = function(simulated, details, startDate, days)
- getWateringQueue = function()
- stopAll = function()

http://docs.rainmachine.apiary.io/#reference/watering
- getParsers = function(id)
- setParserEnable = function(id, enable)
- setParserParams = function(id, params)
- resetParserParams = function(id)
- getParserData = function(id, startDate, days)
- runParser = function(id, withParser, withMixer, withSimulator)
- deleteParser = function(id)

http://docs.rainmachine.apiary.io/#reference/parsers

- getMixer = function(startDate, days)

http://docs.rainmachine.apiary.io/#reference/mixer
- getDiag = function()
- getDiagUpload = function()
- getDiagLog = function()
- sendDiag = function()

http://docs.rainmachine.apiary.io/#reference/diagnostics

- setLogLevel = function(level)
- checkUpdate = function()
- getUpdate = function()
- startUpdate = function()
- getDateTime = function()
- setDateTime = function(dateStr) //dateStr: '%Y-%m-%d %H:%M'
- setSSH = function(isEnabled)
- setTouch = function(isEnabled)
- setLeds = function(isOn)
- reboot = function()
- getTimeZoneDB = function()
- uploadParser = function(fileName, fileType, binData)
- getBeta = function()
- setBeta = function(enabled)

http://docs.rainmachine.apiary.io/#reference/machine
