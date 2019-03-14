Module API4Client
-----------------
This is Python REST client that implements RainMachine API 4.3. The client can be used either though http or https protocols.
Example Usage:

    from rmAPIClient import *
    client = RMAPIClient(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    print client.zones.get()
    print client.programs.get()

More example usages are implemented in each submodule as __main__ function.

Sub-modules
-----------
    API4Client.rmAPIClient
    API4Client.rmAPIClientAuth
    API4Client.rmAPIClientDailyStats
    API4Client.rmAPIClientDev
    API4Client.rmAPIClientDiag
    API4Client.rmAPIClientMachine
    API4Client.rmAPIClientMixer
    API4Client.rmAPIClientParsers
    API4Client.rmAPIClientPrograms
    API4Client.rmAPIClientProvision
    API4Client.rmAPIClientREST
    API4Client.rmAPIClientRestrictions
    API4Client.rmAPIClientWatering
    API4Client.rmAPIClientZones
Module API4Client.rmAPIClientAuth
---------------------------------

Classes
-------
RMAPIClientAuth 
    Authorization (/auth) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientAuth.RMAPIClientAuth
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    restState

    Methods
    -------
    __init__(self, restHandler)

    change(self, oldPass, newPass)
        Changes the device password

    check(self, password)
        Checks if password is valid

    login(self, password, bRemember)
        Authorize access to API calls
        If successfull it will save the OAuth access token for next API calls

    totp(self)
        Generates a One Time Pin to be used for login instead of password
Module API4Client.rmAPIClientDailyStats
---------------------------------------

Classes
-------
RMAPIClientDailyStats 
    Daily statistics (/dailystats) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientDailyStats.RMAPIClientDailyStats
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    get(self, withDetails=False, dateString=None)
        Returns future daily watering statistics, if withDetails is True then it will output statistics for each
        zone on each program 7 days in the future.
Module API4Client.rmAPIClientDev
--------------------------------

Classes
-------
RMAPIClientDev 
    Developer (/dev) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientDev.RMAPIClientDev
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    getbeta(self)
        Returns "enabled": true if device is subscribed to beta quality updates

    setbeta(self, enabled)
        Subscribes or unsubscribes the device from the beta update channel
Module API4Client.rmAPIClientDiag
---------------------------------

Classes
-------
RMAPIClientDiag 
    Diagnostics (/diag) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientDiag.RMAPIClientDiag
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    get(self)
        Returns system diagnostics

    getlog(self)
        Returns the RainMachine log file

    getupload(self)
        Returns diagnostic upload status

    setloglevel(self, level)
        Sets the RainMachine log level: >=20 is INFO and <=10 is DEBUG

    startupload(self)
        Starts diagnostic upload that will send the log files and databases to RainMachine support server
Module API4Client.rmAPIClientMachine
------------------------------------

Classes
-------
RMAPIClientMachine 
    Machine (/machine) related API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientMachine.RMAPIClientMachine
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    checkupdate(self)
        Checks if any updates are available, the results are obtained by getupdate() function

    gettime(self)
        Returns the date and time on device:
        "appDate": "2016-06-27 04:21:57"

    getupdate(self)
        Returns the status of update process and the available packages updates.
        updateStatus can take the following values:
        - STATUS_IDLE = 1
        - STATUS_CHECKING = 2
        - STATUS_DOWNLOADING = 3
        - STATUS_UPGRADING = 4
        - STATUS_ERROR = 5
        - STATUS_REBOOT = 6

    reboot(self)
        Reboots the device

    restart(self)
        Restarts the RainMachine application without rebooting the device

    setleds(self, on)
        Turns on or off the Mini-8 touch panel LED lights

    setssh(self, enabled)
        Enables or disables SSH daemon

    settime(self, datetimeStr)
        Sets the device time, datetimeStr format is %Y-%m-%d %H:%M

    settouch(self, enabled)
        Enables or disables the touch controls on Mini-8 device. This is useful if you either want to prevent
        local access to the device, or if you want to control the touch screen with an external program instead of the
        built in functionality

    shutdown(self)
        Shutsdown the device

    update(self)
        Starts the update process, and will reboot device when the update has finished.
        Ongoing status can be obtaining by polling with getupdate() function
Module API4Client.rmAPIClientMixer
----------------------------------

Classes
-------
RMAPIClientMixer 
    RainMachine Weather Mixer (/mixer) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientMixer.RMAPIClientMixer
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    get(self, dateStr=None, days=30)
        Returns RainMachine weather mixer data. If dateStr (YYYY-MM-DD) is specified it returns results
        from that date for specified number of days (default 30 days)
Module API4Client.rmAPIClient
-----------------------------

Classes
-------
RMAPIClient 
    RainMachine REST API Python wrapper. All function calls returns the data as a python dictionary.
    Calls and their returns are explained here: http://docs.rainmachine.apiary.io/

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClient.RMAPIClient
    __builtin__.object

    Instance variables
    ------------------
    auth

    dailyStats

    dev

    diag

    host

    machine

    mixer

    parsers

    port

    programs

    protocol

    provision

    rest

    restrictions

    state

    watering

    zones

    Methods
    -------
    __init__(self, host, port, protocol=1)

RMAPIClientState 
    Used to cache API calls responses.

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClient.RMAPIClientState

    Instance variables
    ------------------
    cachedData

    Methods
    -------
    __init__(self)
Module API4Client.rmAPIClientParsers
------------------------------------

Classes
-------
RMAPIClientParsers 
    Weather parser (/parser) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientParsers.RMAPIClientParsers
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    activate(self, id, enabled=True)
        Enables or disables a parser. To be executed by RainMachine a parser should be enabled

    delete(self, id)
        Deletes a parser that was uploaded by user.

    get(self, id=None)
        Returns weather parsers parameters and status. If id is not specified it returns data for all existing parsers

    getdata(self, id, dateStr=None, days=None)
        Returns weather data from the specified parser

    run(self, id=-1, withParser=True, withMixer=True, withSimulator=False)
        Forcefully run weather parsers. If id is -1 then all enabled parsers are run.
        If withMixer is true, the RainMachine Weather Mixer will be execute to mix the results from each parsers.

    setdefaults(self, id)
        Set default parameters for specified parser

    setparams(self, id, params)
        Set the specified parameters for specified parser id
Module API4Client.rmAPIClientPrograms
-------------------------------------

Classes
-------
RMAPIClientPrograms 
    RainMachine Schedules/Programs (/program) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientPrograms.RMAPIClientPrograms
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    delete(self, id)
        Deletes a program with specified id

    get(self, id=None)
        Returns a list of all programs available on device

    nextrun(self)
        Returns a list with the date/time for the next run of all programs.

    set(self, data, id=None)
        Creates or modified a program. If id is not specified a new program will be created with the settings
        specified. The data parameter should follow the structure presented here:
        http://docs.rainmachine.apiary.io/#reference/programs

    start(self, id)
        Manually starts watering for specified program

    stop(self, id)
        Removes specified program from watering queue
Module API4Client.rmAPIClientProvision
--------------------------------------

Classes
-------
RMAPIClientPrivisionCloud 
    RainMachine Remote access related setup

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientProvision.RMAPIClientPrivisionCloud
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    get(self)
        Returns the remote access configuration

    reset(self)
        Resets remote access configuration.

    set(self, email, enabled=True)
        Sets the remote access configuration. This is not fully handled by the current python client.
        More details will be added once Remote Access API is publicily available.

RMAPIClientPrivisionWifi 
    WIFI related setup

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientProvision.RMAPIClientPrivisionWifi
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Class variables
    ---------------
    ENCRYPTION_NONE

    ENCRYPTION_PSK

    ENCRYPTION_PSK2

    NETWORK_TYPE_DHCP

    NETWORK_TYPE_STATIC

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    get(self)
        Returns the WIFI configuration

    scan(self)
        Initiate a WIFI scan and returns results of the scan.

    set(self, ssid, encryption, password, dhcp='dhcp', ip=None, mask=None, gateway=None, dns=None)
        Sets up the WIFI networks

RMAPIClientProvision 
    RainMachine setup (/provision) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientProvision.RMAPIClientProvision
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    cloud

    wifi

    Methods
    -------
    __init__(self, restHandler)

    get(self)
        Returns all configuration settings

    reset(self, withReboot=False)
        Perform a factory reset of the current device.

    set(self, systemData, locationData)
        Sets the configuration settings
Module API4Client.rmAPIClientREST
---------------------------------

Classes
-------
RMAPIClientCalls 
    RainMachine currently supported methods

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    GET

    POST

    REST

    Methods
    -------
    __init__(self, restHandler)

RMAPIClientErrors 
    RainMachine client errors and status codes

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientREST.RMAPIClientErrors

    Class variables
    ---------------
    ID

    JSON

    OPEN

    PARAMS

    REQ

RMAPIClientProtocol 
    RainMachine currently supported protocols

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientREST.RMAPIClientProtocol

    Class variables
    ---------------
    HTTP

    HTTPS

    Static methods
    --------------
    getAsString(protocol)

RMAPIClientREST 
    RainMachine REST interface"

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientREST.RMAPIClientREST
    __builtin__.object

    Instance variables
    ------------------
    apiversion

    context

    token

    Methods
    -------
    __init__(self, host='127.0.0.1', port='8080', protocol=1)

    get(self, apiCall, isBinary=False, extraHeaders=None, asJSON=True)

    post(self, apiCall, data=None, isBinary=False, extraHeaders=None, asJSON=True)

    rest(self, type, apiCall, data=None, isBinary=False, extraHeaders=None, asJSON=True)
Module API4Client.rmAPIClientRestrictions
-----------------------------------------

Classes
-------
RMAPIClientRestrictions 
    RainMachine Restrictions (/restrictions) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientRestrictions.RMAPIClientRestrictions
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    currently(self)
        Returns the current active restrictions

    deletehourly(self, id)
        Delete an existing hourly restriction

    globally(self)
        Returns the restrictions configurations for global restrictions like weekdays days, months, freeze protect,
        and hot weather extra watering.

    hourly(self)
        Returns hourly restrictions

    raindelay(self)
        Returns the raindelay start date and seconds left

    setglobal(self, globalRestrictions)
        Set the global restrictions

    sethourly(self, hourlyRestriction)
        Sets a new hourly restriction

    setraindelay(self, days=1)
        Sets a rain delay staring at the moment of the call
Module API4Client.rmAPIClientWatering
-------------------------------------

Classes
-------
RMAPIClientWatering 
    RainMachine Watering (/watering) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientWatering.RMAPIClientWatering
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    getaw(self, dateStr=None, days=30)
        Returns the available water (in soil) for each zone and each program

    getlog(self, withDetails=False, simulated=False, dateStr=None, days=30)
        Returns the past watering log.

    getpast(self, dateStr=None, days=30)
        Returns the evapotranspiration and precipitation forecast used by the already run programs

    getprogram(self)
        Returns the progams that watered or will water today

    getqueue(self)
        Returns the watering queue. The watering queue contains all zones that are scheduled to run and their remaining
        durations

    getzone(self)
        Returns the zone that is currently being watered

    stopall(self)
        Removes all zones from watering queue. This stop current watering completely.
Module API4Client.rmAPIClientZones
----------------------------------

Classes
-------
RMAPIClientZones 
    RainMachine Zones (/zone) API calls

    Ancestors (in MRO)
    ------------------
    API4Client.rmAPIClientZones.RMAPIClientZones
    API4Client.rmAPIClientREST.RMAPIClientCalls

    Instance variables
    ------------------
    baseUrl

    Methods
    -------
    __init__(self, restHandler)

    get(self, id=None)
        Returns the list of zones and their basic setup. If id is specified a single zone is returned

    properties(self, id)
        Returns advanced properties for a zone.

    set(self, id, properties, advanced=None)
        Sets the properties of specified zone.

    start(self, id, duration=300)
        Manually starts watering for specified zone and duration. If duration is not specified
        zone is started with a 5 minutes duration.

    stop(self, id)
        Stops watering the specified zone.
