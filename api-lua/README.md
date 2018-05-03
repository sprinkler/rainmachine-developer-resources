# RainMachine Remote and Local API for LUA

This is RainMachine REST API for LUA 5.1

## Required modules
 - ssl.https
 - socket.http
 - ltn12
 - dkjson or json
 - socket

## Remote API
RMRemoteAPI implements the RainMachine Remote Access service API for accessing devices outside of local network, through https://my.rainmachine.com.
For sample usage please see *rainmachine-remote-example.lua* and modify:

	USER = "your@email.address"
	PASS = "pass"

	EXAMPLE = {
    		name="Test-HD-12",
    		mac="EC:55:F9:1F:EE:3F",
    		id="Ch3g2gvg"
	}
	
The ```EXAMPLE``` parameters can be replaced with the output of :listDevices() function but and it's only required by the example, other implementation can work with device indexes (easier if there is only 1 device) or other methods provided.


## Local Network API
RMLocalAPI implements the RainMachine local network discovery protocol. The discovery procedure works by sending a broadcast UDP message and listening for a well formed responses.
For sample usage please see *rainmachine-local-example.lua* and modify:

	PASS = "PASS"
	EXAMPLE = {
		name="Test-HD-12",
		mac="EC:55:F9:1F:EE:3F"
	}


## Running examples
	lua5.1 ./rainmachine-remote-example.lua
	lua5.1 ./rainmachine-local-example.lua

## Notes
Both remote and local API can be used at the same time. For more information please read the comments inside the source files.


