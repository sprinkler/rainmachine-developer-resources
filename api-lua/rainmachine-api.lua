--luacheck: std lua51,module,read globals luup,ignore 542 611 612 614 111/_,no max line length
-- ----------------------------------------------------------------------------

local https = require("ssl.https")
local http = require("socket.http")
local ltn12 = require("ltn12")
local json = require('dkjson')
require('socket') -- for local discovery API
if json == nil then json = require("json") end
loadfile ("log.lua")()

-- The Remote Access Host used by Remote API
local HOST = "https://my.rainmachine.com"

function rest(url, method, reqbody, access_token)
    local r = {}
    local src = nil
    local length = 0

    if access_token ~= nil then
	url = url .. "?access_token=" .. access_token
    end

    if type(reqbody) == "table" then
	reqbody = json.encode(reqbody)
    end

    if reqbody ~= nil then
	src = ltn12.source.string(reqbody)
	length = string.len(reqbody)
    end
--    D("rest(): %1 : %2", method, url)
--    D("rest(): body: %1", reqbody)

    local response, status, headers = https.request{
        url = url,
        source = src,
        sink = ltn12.sink.table(r),
        method = method,
        headers = {
		["Content-Type"] = "application/json",
		["Content-Length"] = length
	},
        redirect = false
    }

    response = table.concat(r)

    if response == nil or status ~= 200 then
	D("rest(): invalid reply from server")
        return -1, status
    end

--    D("rest(): response: %1", response)

    local data, pos, err = json.decode(response)
    if err then
        L("rest(): unable to decode response, " .. tostring(err))
        D("rest(): response was %1, failed at %2", response, pos)
        return -2, err
    end

    if data.statusCode ~= nil and data.statusCode ~= 0 then
	L("rest(): error %1 %2 ", data.statusCode, data.message)
	return -3, data
    end

--    D("rest(): response: %1", data)
    return 0, data
end


-- ----------------------------------------------------------------------------
-- The RainMachine actual device API
-- 	id: The device ID obtained from remote access service or nil if working on local network
-- 	isLocal: device is accessed through remote service or through local network
-- ----------------------------------------------------------------------------
RMDeviceAPI = {}
function RMDeviceAPI:new(host, id, password, isLocal)
    if id ~= nil then
	url = host .. "/s/" .. id
    else
	url = host -- local network API https port 
    end
    storage = { url=url, id=id, password=password, isLocal=isLocal, access_token=nil }
    self.__index = self
    return setmetatable(storage, self)
end

function RMDeviceAPI:rest(method, path, body)
    L("%1 %2", method, path)
    local url = self.url .. path
    return rest(url, method,  body, self.access_token)
end

function RMDeviceAPI:setPassword(password)
    self.password = password
end

-- Sets a known access_token for this device
function RMDeviceAPI:setAccessToken(token)
    self.access_token = token
end

-- Changes the detected/builtin URL to a custom one (for example if a custom comunication over http is needed)
function RMDeviceAPI:setUrl(url)
    self.url = url
end

--- Device information API

function RMDeviceAPI:getProvision()
    return self:rest("GET", "/api/4/provision")
end

function RMDeviceAPI:getApiVer()
    return self:rest("GET", "/api/4/apiVer")
end

function RMDeviceAPI:getDiag()
    return self:rest("GET", "/api/4/diag")
end


-- Statistics API
function RMDeviceAPI:getDailyStats()
    return self:rest("GET", "/api/4/dailystats")
end

--- Zones API

-- Returns basic zone properties if id is not specified returns all zones
function RMDeviceAPI:getZone(id)
    local url = "/api/4/zone"
    if id ~= nil then
	url = url .. "/" .. id
    end
    return self:rest("GET", url)
end

-- Retrieves all zone parameters if id is not specified returns all zones
function RMDeviceAPI:getZoneProperties(id)
    local url = "/api/4/zone"
    if id ~= nil then
	url = url .. "/" .. id .. "/properties"
    end
    return self:rest("GET", url)
end

-- Starts watering on a zone, duration is in seconds
function RMDeviceAPI:startZone(id, duration)
    local url = "/api/4/zone"
    if id == nil or duration == nil then
	return -1, nil
    end
    url = url .. "/" .. id .. "/start"
    local body = {time=duration}
    return self:rest("POST", url, body)
end

function RMDeviceAPI:stopZone(id)
    local url = "/api/4/zone"
    if id == nil then
	return -1, nil
    end
    url = url .. "/" .. id .. "/stop"
    local body = {zid=id}
    return self:rest("POST", url, body)
end


--- Programs API

function RMDeviceAPI:getProgram(id)
    local url = "/api/4/program"
    if id ~= nil then
	url = url .. "/" .. id
    end
    return self:rest("GET", url)
end

function RMDeviceAPI:startProgram(id)
    local url = "/api/4/program"
    if id == nil then
	return -1, nil
    end
    url = url .. "/" .. id .. "/start"
    local body = {pid=id}
    return self:rest("POST", url, body)
end

function RMDeviceAPI:stopProgram(id)
    local url = "/api/4/program"
    if id == nil then
	return -1, nil
    end
    url = url .. "/" .. id .. "/stop"
    local body = {pid=id}
    return self:rest("POST", url, body)
end

--- Watering Information API
-- Returns the current watering queue zones being watered or pending watering
function RMDeviceAPI:getWateringQueue()
    return self:rest("GET", "/api/4/watering/queue")
end

-- Returns previous watering activities
function RMDeviceAPI:getWateringLog()
    return self:rest("GET", "/api/4/watering/log")
end

-- Stops all watering (including pending) activities
function RMDeviceAPI:stopAll()
    local body = {all=true}
    return self:rest("POST", "/api/4/watering/stopall", body)
end

-- Machine API
function RMDeviceAPI:getTime()
    return self:rest("GET", "/api/4/machine/time")
end

--- Restrictions API
-- Get current restrictions (rain sensor, week, month, freeze)
function RMDeviceAPI:getRestrictions()
    return self:rest("GET", "/api/4/restrictions/currently")
end


-- ----------------------------------------------------------------------------
-- The RainMachine local LAN discovery API. This is used to retrieve locally connected devices on network
-- ----------------------------------------------------------------------------
RMLocalAPI = {}
function RMLocalAPI: new(password)
    storage = { 
	password = password,
	devices = {}
    }
    setmetatable(storage, self)
    self.__index = self
    return storage
end

-- Send a UDP broadcast and listens for replies from RainMachine (a string with tokens separated by ||)
function RMLocalAPI: discover()
    local ADVERTISE_PORT = 15800
    local RESPONSE_PORT = 15900
    local BROADCAST = '255.255.255.255'

    local delay = 0.1
    local loops = 20
    local found = false
    udpAdvertise = assert (socket.udp())
    assert(udpAdvertise:setoption('broadcast', true))

    udpResponse = assert (socket.udp())
    assert (udpResponse:setsockname ('*', RESPONSE_PORT))
    udpResponse:settimeout(1)

    assert (udpAdvertise:sendto('discover', BROADCAST, ADVERTISE_PORT))

    while loops > 0 do
	local message = udpResponse:receive(1024)
	if (message ~= nil) then
	    local deviceInfo = self:parseMessage(message)
	    local device = {
		instance=RMDeviceAPI:new(deviceInfo["url"], nil, self.password, true),
		id=nil,
		name=deviceInfo["name"],
		mac=deviceInfo["mac"],
	    }
	    table.insert(self.devices, device)
	    D("%1 %2 %3", device.name, device.mac, device.instance.url)
	    found = true
	end
	socket.sleep(0.1)
	loops = loops - 1
    end
    return found
end

function RMLocalAPI:parseMessage(message)
    local deviceInfo = {}
    local tokens = {}
    for i in string.gmatch(message, "([^||]+)") do
	table.insert(tokens, i)
    end
    if #tokens > 4 then
	deviceInfo["mac"] = tokens[2]
	deviceInfo["name"] = tokens[3]
	deviceInfo["url"] = tokens[4]
	deviceInfo["configured"] = tokens[5]
    end
    return deviceInfo
end

-- Authenticate with a specified device
function RMLocalAPI:authDevice(device)
    body = {pwd=device.instance.password, remember=1}
    status, result = device.instance:rest("POST", "/api/4/auth/login", body)
    if status == 0 then
	-- Selected sprinkler access_token
	device.instance.access_token = result.access_token
	L("Local Auth with %1 OK %2", device.name, result)
	return true
    end
    return false
end

function RMLocalAPI:getDevices()
    return self.devices
end

function RMLocalAPI:getDeviceByName(name)
    for i = 1, #self.devices do
	if self.devices[i].name == name then
	    return self.devices[i]
	end
    end
    return nil
end

function RMLocalAPI:getDeviceByMac(mac)
    for i = 1, #self.devices do
	if string.lower(self.devices[i].mac) == string.lower(mac) then
	    return self.devices[i]
	end
    end
    return nil
end

function RMLocalAPI:listDevices()
    for i=1, #self.devices do
	L("%1 %2 %3", self.devices[i].name, self.devices[i].mac, self.devices[i].instance.url)
    end
end



-- ----------------------------------------------------------------------------
-- The RainMachine Remote Access API. This is used to retrieve the connected devices and auth with each connected device
-- password should match on at least one device to list the devices associated with account
-- to authenticate with devices with different passwords see setPassword() for setting a password for each device
-- ----------------------------------------------------------------------------
RMRemoteAPI = {}
function RMRemoteAPI:new(email, password)
    storage = { 
	email=email, 
	password=password,
	access_token = nil,
	devices = {}
    }
    setmetatable(storage, self)
    self.__index = self
    return storage
end

-- Set a previously saved access token
function RMRemoteAPI:setAccessToken(token)
    self.access_token = token
end

-- Authenticate with Remote Access Service
function RMRemoteAPI:auth(force)
    if force==true then
	self.access_token = nil
    end
    if self.access_token ~= nil then
	return true-- Already auth 
    end

    local body = {user={email=self.email, pwd=self.password, remember=1}}
    -- login with remote service the password should match at least one device from the account
    local status, result = self:rest("POST", "/login/auth", body)

    if status == 0 then
	-- RainMachine remote access access token so we can call next APIs
	self.access_token = result.access_token
	-- Get the list of sprinklers associated with the account
	local status, result = self:rest("POST", "/devices/get-sprinklers", body)
	if status == 0 then
	    if (table.getn(result.sprinklers) > 0) then
		for i= 1,#result.sprinklers do
		    -- Remote device unique ID (always the same) or IP addres if detected locally
		    local devid=result.sprinklers[i].sprinklerId
		    -- Device MAC address
		    local devmac=result.sprinklers[i].mac
		    -- Device Name
		    local devname=result.sprinklers[i].name
		    -- there might be different password for different devices
		    local devpassword=self.password
		    local device = {
			instance=RMDeviceAPI:new(HOST, devid, devpassword, false),
			id=devid,
			name=devname,
			mac=devmac,
		    }
		    self.devices[i] = device
		    --L("\t%1 (%2:%3)", devname, devid, devmac)
		end
		return true
	    end
	end
    end
    return false
end

function RMRemoteAPI:rest(method, path, body)
    L("%1 %2", method, path)
    local url = HOST .. path
    return rest(url, method, body, self.access_token)
end

-- Authenticate with a specified device
function RMRemoteAPI:authDevice(device)
    body = {sprinklerId=device.id, pwd=device.instance.password, remember=1}
    status, result = self:rest("POST", "/devices/login-sprinkler", body)
    if status == 0 then
	-- Selected sprinkler access_token
	device.instance.access_token = result.access_token
	L("Remote Auth with %1 OK %2", device.name, result)
	return true
    end
    return false
end

function RMRemoteAPI:getDevices()
    return self.devices
end

function RMRemoteAPI:getDeviceById(id)
    for i = 1, #self.devices do
	if self.devices[i].id == id then
	    return self.devices[i]
	end
    end
    return nil
end

function RMRemoteAPI:getDeviceByName(name)
    for i = 1, #self.devices do
	if self.devices[i].name == name then
	    return self.devices[i]
	end
    end
    return nil
end

function RMRemoteAPI:getDeviceByMac(mac)
    for i = 1, #self.devices do
	if self.devices[i].mac == mac then
	    return self.devices[i]
	end
    end
    return nil
end

function RMRemoteAPI:listDevices()
    for i=1, #self.devices do
	L("%1 (%2:%3)", self.devices[i].name, self.devices[i].id, self.devices[i].mac)
    end
end

function RMRemoteAPI:rest(method, path, body)
    L("%1 %2", method, path)
    local url = HOST .. path
    return rest(url, method, body, self.access_token)
end
