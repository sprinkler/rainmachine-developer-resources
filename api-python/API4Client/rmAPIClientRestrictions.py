# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *


class RMAPIClientRestrictions(RMAPIClientCalls):

    """
    RainMachine Restrictions (/restrictions) API calls
    """

    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "restrictions"

    def currently(self):
        """
        Returns the current active restrictions
        """
        return self.GET(self.baseUrl + "/currently")

    def globally(self):
        """
        Returns the restrictions configurations for global restrictions like weekdays days, months, freeze protect,
        and hot weather extra watering.
        """
        return self.GET(self.baseUrl + "/global")

    def hourly(self):
        """
        Returns hourly restrictions
        """
        return self.GET(self.baseUrl + "/hourly")

    def raindelay(self):
        """
        Returns the raindelay start date and seconds left
        """
        return self.GET(self.baseUrl + "/raindelay")

    def setglobal(self, globalRestrictions):
        """
        Set the global restrictions
        """
        return self.POST(self.baseUrl + "/global", globalRestrictions)

    def sethourly(self, hourlyRestriction):
        """
        Sets a new hourly restriction
        """
        return self.POST(self.baseUrl + "/hourly", hourlyRestriction)

    def setraindelay(self, days = 1):
        """
        Sets a rain delay staring at the moment of the call
        """
        data = {"rainDelay": days}
        return self.POST(self.baseUrl + "/raindelay", data)

    def deletehourly(self, id):
        """
        Delete an existing hourly restriction
        """
        if id is not None:
            return self.POST(self.baseUrl + "/hourly/" + str(id) + "/delete")
        return RMAPIClientErrors.ID



# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    restrictions = RMAPIClientRestrictions(restLocal)

    currently = restrictions.currently()
    print currently

    globally = restrictions.globally()
    globalRestrictionData = {
        "hotDaysExtraWatering": False,
        "freezeProtectEnabled": False,
        "freezeProtectTemp": 2.0,
        "noWaterInWeekDays": "1111111",
        "noWaterInMonths": "111111111111",
        "rainDelayStartTime": 1466669477,
        "rainDelayDuration": 86400
    }
    restrictions.setglobal(globalRestrictionData)
    print "Global restrictions: %s" % restrictions.globally()
    restrictions.setglobal(globally)
    print "Global restrictions: %s" % restrictions.globally()

    hourlyRestrictionData = {
        "start": 14 * 60 + 30, # 14:30
        "duration": 30,
        "weekdays": "1111111"
    }

    hourlyRestriction = restrictions.sethourly(hourlyRestrictionData)
    print "Added new hourly restriction: %s" % hourlyRestriction
    print "Current hourly restrictions %s" % restrictions.hourly()
    restrictions.deletehourly(hourlyRestriction["restriction"]["uid"])
    hourly = restrictions.hourly()
    print "Current hourly restrictions %s" % hourly


    restrictions.setraindelay(1)
    restrictions.setraindelay(0)
    raindelay = restrictions.raindelay()
    print "Current Raindelay: %s" % raindelay

    assert currently.get('rainDelayCounter', None) is not None
    assert globally.get('hotDaysExtraWatering', None) is not None
    assert raindelay.get('delayCounter', None) is not None
    assert hourly.get('hourlyRestrictions', None) is not None


