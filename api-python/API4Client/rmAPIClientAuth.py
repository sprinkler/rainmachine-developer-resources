# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *

class RMAPIClientAuth(RMAPIClientCalls):
    """
    Authorization (/auth) API calls
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.restState = restHandler

    def login(self, password, bRemember):
        """
        Authorize access to API calls
        If successfull it will save the OAuth access token for next API calls
        """
        loginValues = dict(pwd=password, remember=bRemember)
        data = self.POST("auth/login", loginValues)
        if data is not None:
            token = data.get("access_token", None)
            if token is not None:
                self.restState.token = token
                return True
        return False


    def change(self, oldPass, newPass):
        """
        Changes the device password
        """
        loginValues = dict(newPass=newPass, oldPass=oldPass)
        data = self.POST("auth/change", loginValues)
        if data is not None:
            token = data.get("access_token", None)
            if token is not None:
                self.restState.token = token
                return True
        return False

    def check(self, password):
        """
        Checks if password is valid
        """
        loginValues = dict(pwd=password)
        data = self.GET("auth/check", loginValues)
        if data is not None:
            if data["statusCode"] == 0:
                return True

        return False

    def totp(self):
        """
        Generates a One Time Pin to be used for login instead of password
        """
        data = self.GET("auth/totp")
        if data is not None:
            return data["totp"]

        return None


if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="8080", protocol=RMAPIClientProtocol.HTTPS)
    restNotWorking = RMAPIClientREST(host="127.2.0.1", port="80")
    auth = RMAPIClientAuth(restLocal)
    assert auth.login("", True) == True
    auth = RMAPIClientAuth(restNotWorking)
    assert auth.login("admin", True) == False
