/*
 *	Copyright (c) 2015 RainMachine, Green Electronics LLC
 *	All rights reserved.
 */

var APIAsync = new _API(true);
var APISync = new _API(false);

var API = APISync;

function _API(async) {

var host = window.location.hostname;
//var host = "private-bd9e-rainmachine.apiary-mock.com";
//var host = "127.0.0.1";
//var host = "5.2.191.144";

var port = window.location.port;
//var port = "443";
//var port = "18080";
//var port = "8888";


//var protocol = window.location.protocol;

var apiUrl = "https://" + host + ":" + port + "/api/4";
//var apiUrl = "http://" + host + ":" + port + "/api/4";

var token = null;
var async = async;

function rest(type, apiCall, data, isBinary, extraHeaders)
{
	var url;
	var a = new Async();
	var r = new XMLHttpRequest();

	if (token !== null)
		url = apiUrl + apiCall + "?access_token=" + token;
	else
		url = apiUrl + apiCall;

	//console.log("%s API call: %s", async ? "ASYNC":"*sync*", url);

	if (async) {
		r.onload = function() {
			if (r.readyState === 4) {
				if (r.status === 200) {
					//console.info("REST ASYNC: SUCCESS  %s reply: %o", url, r);
					a.resolve(JSON.parse(r.responseText));
				} else {
					console.error("REST ASYNC: FAIL reply for %s, ready: %s, status: %s", url, r.readyState, r.status);
					a.reject(r.status);
				}
			}
		};
	};

	try {
		r.open(type, url, async);

		if (extraHeaders) {
			while (header = extraHeaders.shift()) {
				r.setRequestHeader(header[0], header[1]);
			}
		}

		//r.setRequestHeader("Content-type", "application/json");
		if (type === "POST") {
			if (isBinary) {
				r.send(data);
			} else {
				r.setRequestHeader("Content-type", "text/plain");
				r.send(JSON.stringify(data));
			}
		} else	{
			r.send();
		}

		if (async)
			return a;
		else
			return JSON.parse(r.responseText);

	} catch(e) { console.log(e);}

	console.log("REST: NULL return");
	return null;
}

this.post = function(apiCall, data) { return rest("POST", apiCall, data, false, null); }
this.get = function(apiCall) { return rest("GET", apiCall, null, false, null); }
this.uploadFile = function(apiCall, data, extraHeaders) { return rest("POST", apiCall, data, true, extraHeaders); }
this.setAccessToken = function(accessToken) { token = accessToken; }


/* ------------------------------------------ API ROOT PATHS ----------------------------------------------*/
this.URL = Object.freeze({
	auth			: "/auth",
	provision		: "/provision",
	dailystats		: "/dailystats",
	restrictions	: "/restrictions",
	program			: "/program",
	zone			: "/zone",
	watering		: "/watering",
	parser			: "/parser",
	mixer			: "/mixer",
	diag			: "/diag",
	machine			: "/machine",
	dev				: "/dev"
});

/* ------------------------------------------ API ERROR CODES ----------------------------------------------*/
this.ERROR = {
    Success                 : '{ "statusCode":  0,  "message": "OK"                         }',
    ExceptionOccurred       : '{ "statusCode":  1,  "message": "Exception occurred !"       }',
    NotAuthenticated        : '{ "statusCode":  2,  "message": "Not Authenticated !"        }',
    InvalidRequest          : '{ "statusCode":  3,  "message": "Invalid request !"          }',
    NotImplemented          : '{ "statusCode":  4,  "message": "Not implemented yet !"      }',
    NotFound                : '{ "statusCode":  5,  "message": "Not found !"                }',
    DBError                 : '{ "statusCode":  6,  "message": "DB Error !"                 }',
    ProvisionFailed         : '{ "statusCode":  7,  "message": "Cannot provision unit"      }',
    PasswordNotChanged      : '{ "statusCode":  8,  "message": "Cannot change password"     }',
    ProgramValidationFailed : '{ "statusCode":  9,  "message": "Invalid program constraints"}'
};

};

/* ------------------------------------------ VER API CALLS -----------------------------------------------*/

_API.prototype.getApiVer = function()
{
	var url = "/apiVer";
	return this.get(url, null);
}

/* ------------------------------------------ AUTH API CALLS ----------------------------------------------*/

_API.prototype.auth = function(password, remember)
{
	var url = this.URL.auth + "/login";
	
	var data = 
	{
		pwd: password,
		remember: remember
	};
	
	var reply = this.post(url, data, null);
	console.log(JSON.stringify(reply, null, "  "));

	var token = reply.access_token;
	this.setAccessToken(token);
	return token;
};

_API.prototype.totp = function()
{
	var url = this.URL.auth + "/totp";
	return this.get(url, null);
};

_API.prototype.authChange = function(oldPass, newPass)
{
    var url = this.URL.auth + "/change";

    var data =
    {
    	newPass: newPass,
    	oldPass: oldPass
    }

    return this.post(url, data, null);
}

/* ------------------------------------------ PROVISION API CALLS -----------------------------------------*/

_API.prototype.getProvision = function()
{
	return this.get(this.URL.provision, null);
}

_API.prototype.getProvisionWifi = function()
{
	var url = this.URL.provision + "/wifi";
	return this.get(url, null);
}

_API.prototype.getProvisionCloud = function()
{
	var url = this.URL.provision + "/cloud";
	return this.get(url, null);
}

_API.prototype.getProvisionDOY = function()
{
	var url = this.URL.provision + "/doy";
	return this.get(url, null);
}

_API.prototype.setProvision = function(systemObj, locationObj)
{
	var url = this.URL.provision;
	var data = {};

	if (systemObj !== undefined && systemObj !== null)
		data.system = systemObj;

	if (locationObj !== undefined && locationObj !== null)
    	data.location = locationObj;

    if (Object.keys(data).length == 0)
    	return this.ERROR.InvalidRequest;

    return this.post(url, data, null);
}

_API.prototype.setProvisionName = function(name)
{
	var url = this.URL.provision +  "/name";
	var data = { netName: name };

	return this.post(url, data,  null);
}

_API.prototype.setProvisionCloud = function(cloudObj)
{
	var url = this.URL.provision +  "/cloud";
	var data = cloudObj;

	return this.post(url, data, null);
}

_API.prototype.setProvisionCloudEmail = function(email)
{
	var url = this.URL.provision +  "/cloud/mail";
	var data = { email: email };

	return this.post(url, data, null);
}

_API.prototype.setProvisionCloudEnable = function(isEnabled)
{
	var url = this.URL.provision +  "/cloud/enable";
	var data = { enable: isEnabled };

	return this.post(url, data, null);
}

_API.prototype.setProvisionCloudReset = function()
{
	var url = this.URL.provision +  "/cloud/reset";
	var data = { };

	return this.post(url, data, null);
}

_API.prototype.setProvisionReset = function(withRestart)
{
	var url = this.URL.provision + "/reset";
	var data = { restart: withRestart };

	return this.post(url, data, null);
}

/* ------------------------------------------ DAILY STATS API CALLS ---------------------------------------*/

_API.prototype.getDailyStats = function(dayDate, withDetails)
{
	var url = this.URL.dailystats;

	if (dayDate !== undefined && dayDate !== null) // current API doesn't support daily stats details with specified day
	{
		url += "/" + dayDate;
		return this.get(url, null);
	}

	if (withDetails !== undefined && withDetails)
		url += "/details";

	return this.get(url, null);
}

/* ----------------------------------------- RESTRICTIONS API CALLS ---------------------------------------*/

_API.prototype.getRestrictionsRainDelay = function()
{
	var url = this.URL.restrictions + "/raindelay";
	return this.get(url, null);
}

_API.prototype.getRestrictionsGlobal = function()
{
	var url = this.URL.restrictions + "/global";
	return this.get(url, null);
}

_API.prototype.getRestrictionsHourly = function()
{
	var url = this.URL.restrictions + "/hourly";
	return this.get(url, null);
}

_API.prototype.getRestrictionsCurrently = function()
{
	var url = this.URL.restrictions + "/currently";
	return this.get(url, null);
}

_API.prototype.setRestrictionsRainDelay = function(days)
{
	var url = this.URL.restrictions + "/raindelay";
	var data = { rainDelay: days };

	return this.post(url, data, null);
}

_API.prototype.setRestrictionsGlobal = function(globalRestrictionObj)
{
	var url = this.URL.restrictions + "/global";
	var data = globalRestrictionObj;

	return this.post(url, data, null);
}

_API.prototype.setRestrictionsHourly = function(hourlyRestrictionObj)
{
	var url = this.URL.restrictions + "/hourly";
	var data = hourlyRestrictionObj;

	return this.post(url, data, null);
}

_API.prototype.deleteRestrictionsHourly = function(id)
{
    var url = this.URL.restrictions + "/hourly/" + id + "/delete";
    var data = {};

    return this.post(url, data, null);
}

/* ----------------------------------------- PROGRAMS API CALLS -------------------------------------------*/
_API.prototype.getPrograms = function(id)
{
	var url = this.URL.program;

	if (id !== undefined)
		url += "/" + id;

	return this.get(url, null);
}

_API.prototype.getProgramsNextRun = function()
{
	var url = this.URL.program + "/nextrun";

	return this.get(url, null);
}

_API.prototype.setProgram = function(id, programProperties)
{
	var url = this.URL.program + "/" + id;
	var data = programProperties;

	return this.post(url, data, null);
}

_API.prototype.newProgram = function(programProperties)
{
	var url = this.URL.program;
	var data = programProperties;

	return this.post(url, data, null);
}

_API.prototype.deleteProgram = function(id)
{
	var url = this.URL.program + "/" + id + "/delete";
    var data = { pid: id };

    return this.post(url, data, null);
}

_API.prototype.startProgram = function(id)
{
	var url = this.URL.program + "/" + id + "/start";
    var data = { pid: id };

    return this.post(url, data, null);
}

_API.prototype.stopProgram = function(id)
{
	var url = this.URL.program + "/" + id + "/stop";
    var data = { pid: id };

    return this.post(url, data, null);
}

/* ------------------------------------------ ZONES API CALLS --------------------------------------------*/
_API.prototype.getZones = function(id)
{
	var url = this.URL.zone;

	if (id !== undefined)
		url += "/" + id;

	return this.get(url, null);
}

_API.prototype.startZone = function(id, duration)
{
	if (id === undefined || id === null)
		return this.ERROR.InvalidRequest;

	if (duration === undefined || duration === null)
		return this.ERROR.InvalidRequest;

	var url = this.URL.zone + "/" + id + "/start";
	var data = { time: duration };

	return this.post(url, data, null);
}

_API.prototype.stopZone = function(id)
{
	if (id === undefined || id === null)
		return this.ERROR.InvalidRequest;

	var url = this.URL.zone + "/" + id + "/stop";

	var data = { zid : id };

	return this.post(url, data, null);
}

_API.prototype.getZonesProperties = function(id)
{
	var url = this.URL.zone;

	if (id !== undefined)
		url += "/" + id;

	url += "/properties";

	return this.get(url, null);
}

_API.prototype.setZonesProperties = function(id, properties, advancedProperties)
{
	var url = this.URL.zone;

	if (id === undefined)
		return this.ERROR.InvalidRequest;

	if (properties === undefined || properties === null)
		return this.ERROR.InvalidRequest;


	url += "/" + id + "/properties";

	var data = properties;

	if (advancedProperties !== undefined && advancedProperties !== null)
		data.waterSense = advancedProperties;

	return this.post(url, data, null);
}

_API.prototype.simulateZone = function(properties, advancedProperties) {
	var url = this.URL.zone + "/simulate";
	var data = properties;

	if (advancedProperties !== undefined && advancedProperties !== null)
		data.waterSense = advancedProperties;

	return this.post(url, data, null);
};

/* ----------------------------------------- WATERING API CALLS -------------------------------------------*/

_API.prototype.getWateringLog = function(simulated, details, startDate, days)
{
	var url = this.URL.watering + "/log" + (simulated ? "/simulated" : "") + (details ? "/details" : "");

	//start date format YYYY-DD-MM
	if (startDate !== null && startDate.length > 9)
		url += "/" + startDate;

	if (days !== null && days > 0)
		url += "/" + days;

	return this.get(url, null);
}

_API.prototype.getWateringQueue = function()
{
	var url = this.URL.watering + "/queue";

	return this.get(url, null);
}

_API.prototype.getWateringPast = function(startDate, days)
{
	var url = this.URL.watering + "/past";

	//start date format YYYY-DD-MM
	if (startDate !== null && startDate.length > 9)
		url += "/" + startDate;

	if (days !== null && days > 0)
		url += "/" + days;

	return this.get(url, null);
}

_API.prototype.getWateringAvailable = function(startDate, days)
{
	var url = this.URL.watering + "/available";

	//start date format YYYY-DD-MM
	if (startDate !== null && startDate.length > 9)
		url += "/" + startDate;

	if (days !== null && days > 0)
		url += "/" + days;

	return this.get(url, null);
}

_API.prototype.stopAll = function()
{
	var url = this.URL.watering + "/stopall";
	var data = { all: true };

	return this.post(url, data, null);
}

/* ------------------------------------------ PARSER API CALLS --------------------------------------------*/
_API.prototype.getParsers = function(id)
{
	var url = this.URL.parser;

	if (id !== undefined)
		url += "/" + id;

	return this.get(url, null);
}

_API.prototype.setParserEnable = function(id, enable)
{
	var url = this.URL.parser;

	if (id === undefined || id === null)
		return this.ERROR.InvalidRequest;

	url += "/" + id + "/activate";

	var data = { activate: enable };

	return this.post(url, data, null);
}

_API.prototype.setParserParams = function(id, params)
{
	var url = this.URL.parser;

	if (id === undefined || id === null)
		return this.ERROR.InvalidRequest;

    url += "/" + id + "/params";

    return this.post(url, params, null);
}

_API.prototype.resetParserParams = function(id)
{
	var url = this.URL.parser;

	if (id === undefined || id === null)
		return this.ERROR.InvalidRequest;

	url += "/" + id + "/defaults";

	return this.post(url, {}, null)
}

_API.prototype.getParserData = function(id, startDate, days)
{
	var url = this.URL.parser;

	if (id === undefined || id === null)
    		return this.ERROR.InvalidRequest;

	url += "/" + id + "/data";

	if (startDate !== undefined)
		url += "/" + startDate;

	if (days !== undefined)
		url += "/" + days;

	return this.get(url, null);
}


_API.prototype.runParser = function(id, withParser, withMixer, withSimulator)
{
	var url = this.URL.parser;
	url += "/run";

	var data = {
		parser: withParser,
		mixer: withMixer,
		simulator: withSimulator
	};

	if (typeof id !== undefined && id !== null && id >= 0) {
		data.parserID = id;
	}

    return this.post(url, data, null);
}

_API.prototype.deleteParser = function(id)
{
	var url = this.URL.parser;

	if (id === undefined || id === null)
		return this.ERROR.InvalidRequest;

	url += "/" + id + "/delete";

	return this.post(url, {}, null)
}


/* ------------------------------------------ MIXER API CALLS ---------------------------------------------*/
_API.prototype.getMixer = function(startDate, days)
{
	var url = this.URL.mixer;

	if (startDate !== undefined)
		url += "/" + startDate;

	if (days !== undefined)
		url += "/" + days;

	return this.get(url, null);
}

/* ------------------------------------------ DIAG API CALLS ------------------------------------------------*/
_API.prototype.getDiag = function()
{
	return this.get(this.URL.diag, null)
}

_API.prototype.getDiagUpload = function()
{
	var url = this.URL.diag + "/upload";
	return this.get(url, null);
}

_API.prototype.getDiagLog = function()
{
	var url = this.URL.diag + "/log";
	return this.get(url, null);
}

_API.prototype.sendDiag = function()
{
    var url = this.URL.diag + "/upload";
    return this.post(url, {}, null);
}

_API.prototype.setLogLevel = function(level)
{
	var url = this.URL.diag + "/log/level";
	var data  = { level: level };
	return this.post(url, data, null);
}

/* ------------------------------------------ MACHINE API CALLS ---------------------------------------------*/

_API.prototype.checkUpdate = function()
{
	var url = this.URL.machine + "/update/check";
	return this.post(url, {}, null);
}

_API.prototype.getUpdate = function()
{
	var url = this.URL.machine + "/update";
	return this.get(url, null);
}

_API.prototype.startUpdate = function()
{
	var url = this.URL.machine + "/update";
	return this.post(url, {}, null);
}

_API.prototype.getDateTime = function()
{
	var url = this.URL.machine + "/time";
	return this.get(url, null);
}

_API.prototype.setDateTime = function(dateStr) //dateStr: '%Y-%m-%d %H:%M'
{
	var url = this.URL.machine + "/time";
	var data = { appDate: dateStr };
	return this.post(url, data, null);
}

_API.prototype.setSSH = function(isEnabled)
{
	var url = this.URL.machine + "/ssh";
	var data = { enabled: isEnabled };

	return this.post(url, data, null);
}

_API.prototype.setTouch = function(isEnabled)
{
	var url = this.URL.machine + "/touch";
	var data = { enabled: isEnabled };

	return this.post(url, data, null);
}

_API.prototype.setLeds = function(isOn)
{
	var url = this.URL.machine + "/lightleds";
	var data = { enabled: isEnabled };

	return this.post(url, data, null);
}


_API.prototype.reboot = function()
{
	var url = this.URL.machine + "/reboot";
	var data = {};

	return this.post(url, data, null);
}

_API.prototype.getShortDetection = function()
{
	var url = this.URL.machine + "/shortdetection";
	return this.get(url, null);
}

_API.prototype.setShortDetection = function(enabled)
{
	var url = this.URL.machine + "/shortdetection";
	var data = {
		watchforshort: 0,
		watchforload: 0
	};

	if (enabled) {
		data.watchforshort = 1;
		data.watchforload = 2;
	}

	return this.post(url, data, null);
}

/* ------------------------------------------ DEV API CALLS -------------------------------------------------*/

_API.prototype.getTimeZoneDB = function()
{
	var url = this.URL.dev + "/timezonedb.json";

	return this.get(url, null);
}

_API.prototype.uploadParser = function(fileName, fileType, binData)
{
	var url = this.URL.dev + "/import/parser";
	var extraHeaders = [];

	extraHeaders.push(["Content-Type", fileType]);
	extraHeaders.push(["Content-Disposition", "inline; filename=" + fileName]);

	return this.uploadFile(url, binData, extraHeaders);
}

_API.prototype.getBeta = function()
{
	var url = this.URL.dev + "/beta";
	return this.get(url, null);
}

_API.prototype.setBeta = function(enabled)
{
	var url = this.URL.dev + "/beta";
	var data = { enabled: enabled };
	return this.post(url, data, null);
}

