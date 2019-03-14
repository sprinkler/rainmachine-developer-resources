loadfile ("rainmachine-api.lua")()

USER = "your@email.address"
PASS = "pass"

EXAMPLE = {
    name="Test-HD-12",
    mac="EC:55:F9:1F:EE:3F",
    id="Ch3g2gvg"
}

local rm = RMRemoteAPI:new(USER, PASS)
if rm:auth() == true then
    rm:listDevices()
    d = rm:getDeviceById(EXAMPLE.id)
    if d ~= nil then
	L("Name: %1", d.name)
    end
    d = rm:getDeviceByName(EXAMPLE.name)
    if d ~= nil then
	L("Id: %1", d.id)
    end
    L("Device instance id: %1", d.instance.id)
    if rm:authDevice(d) == false then
	L("Cannot auth device %1 with password %2", d.name, d.password)
    else
	L("Authenticated with access_token: %1", d.instance.access_token)
	local s, provision = d.instance:getProvision()
	local s, api = d.instance:getApiVer()
	L("RainMachine: %1 API: %2 Hardware: %3, Software: %4", provision.system.netName, api.apiVer, api.hwVer, api.swVer)
	local s, diag = d.instance:getDiag()
	local s, zones = d.instance:getZone()
	local s, programs = d.instance:getProgram()
	local s, restrictions = d.instance:getRestrictions()

	L("Zones: ")
	for i=1,#zones.zones do
	    L("\t(%1) %2", zones.zones[i].uid, zones.zones[i].name)
	end
	L("Programs: ")
	for i=1,#programs.programs do
	    L("\t(%1) %2", programs.programs[i].uid, programs.programs[i].name)
	    local pzones = programs.programs[i].wateringTimes
	    for j=1,#pzones do
		if pzones[j].active == true then
		    if pzones[j].duration ~= 0 then
			L("\t\t%1: %2 seconds", pzones[j].name, pzones[j].duration)
		    else
			L("\t\t%1: auto", pzones[j].name, pzones[j].duration)
		    end
		end
	    end
	end
	L("Restrictions: %1", restrictions)
--	local s, reply = d.instance:startZone(2, 10 * 60)
	local s, watering_queue = d.instance:getWateringQueue()
	L("Water Queue: %1", watering_queue)
	local s, post = d.instance:stopAll()
    end
end

