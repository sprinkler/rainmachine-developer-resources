# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from collections import OrderedDict
import hashlib, uuid, random
import hmac
import struct
import time

from RMDataFramework.rmAuthData import RMAuthToken
from RMDatabaseFramework.rmUserSettingsTable import RMAuthTokensTable, RMUserSettingsTable
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp
from RMUtilsFramework.rmLogging import log

class RMAuth:
    def __init__(self):
        self.__password = self.__encryptPassword("")
        self.__tokens = OrderedDict()
        self.__isLoaded = False
        self.__tokenLongExpirationTimeout = 5 * 365 * 24 * 3600 # ~5 years # TODO: OpenWRT time_t is 32bit Y2038 problem
        self.__tokenShortExpirationTimeout = 1 * 24 * 3600 # 1 day

        self.__settingsTable = None
        self.__tokensTable = None

    def setDatabases(self, settingsDatabase):
        self.__settingsTable = RMUserSettingsTable(settingsDatabase)
        self.__tokensTable = RMAuthTokensTable(settingsDatabase)

    def load(self):
        if not self.__isLoaded:
            password = self.__settingsTable.getPassword()
            if password:
                self.__password = password

            self.__tokensTable.deleteExpiredRecords(rmCurrentTimestamp())

            self.__tokens = self.__tokensTable.getAllRecords(True)
            self.__isLoaded = True

    def factoryReset(self):
        self.__password = self.__encryptPassword("")

        self.__tokens.clear()
        self.__tokensTable.deleteAllRecords()

        self.__settingsTable.savePassword(self.__password)

    def  doPasswordsMatch (self, password):
        if self.__password == self.__encryptPassword(password):
            return True
        return False

    def authenticateByPassword(self, password, remember, oldAccessToken):
        self.__deleteExpiredTokens()
        if self.doPasswordsMatch(password):
            self.__deleteAccessToken(oldAccessToken)
            return self.__generateToken(remember), self.__manglePassword(self.__password)
        return None, None

    def authenticateByToken(self, token):
        self.__deleteExpiredTokens()
        return self.__tokens.get(token, None)

    def authenticateByTOTP(self, totp):
        if self.validateTOTP(totp, length=6, interval=14400, drift=2):
            return self.__generateToken(longLiveToken=False)
        return None

    def changePassword(self, oldPassword, newPassword, oldAccessToken, requireOldPassword = True):
        if requireOldPassword and self.__encryptPassword(oldPassword) != self.__password:
            return None, None
        if not newPassword or len(newPassword) < 3:
            return None, None

        token = self.__tokens.get(oldAccessToken, None)

        self.__password = self.__encryptPassword(newPassword)
        self.__tokens.clear()

        self.__settingsTable.savePassword(self.__password)
        self.__tokensTable.deleteAllRecords()

        if token is None:
            token = self.__generateToken()
        else:
            self.__tokens[token.token] = token
            self.__tokensTable.addRecord(token.token, token.expiration)

        return token, self.__manglePassword(self.__password)

    def changePasswordEx(self, mangleddPassword, oldAccessToken):
        if not mangleddPassword or len(mangleddPassword) < len(self.__password):
            return None, None

        token = self.__tokens.get(oldAccessToken, None)
        encryptedPassword = self.__unmanglePassword(mangleddPassword)

        self.__password = encryptedPassword
        self.__tokens.clear()

        self.__settingsTable.savePassword(self.__password)
        self.__tokensTable.deleteAllRecords()

        if token is None:
            token = self.__generateToken()
        else:
            self.__tokens[token.token] = token
            self.__tokensTable.addRecord(token.token, token.expiration)

        return token, self.__manglePassword(self.__password)

    # Functions to generate/validate a TOTP
    # follows http://jacob.jkrall.net/totp/
    def generateTOTP(self, length=6, interval=30, asString=True, clock=None):
        if clock is None:
            clock = time.time()
        secret = self.__password
        counter = int(clock) // interval
        message = struct.pack(">Q", counter)
        hmacDigest = hmac.new(secret, message, hashlib.sha1).digest() # HMAC-SHA-1(SECRET, time()/30)
        lastByte = ord(hmacDigest[-1])
        offset = lastByte & 0xF # last nibble
        (dbc1, ) = struct.unpack(">I", hmacDigest[offset:offset + 4])  # Dynamic Binary Code #1
        dbc2 = dbc1 & 0x7fffffff # 31 bit number with top bit cleared # Dynamic Binary Code #2

        if asString:
            digits = str(dbc2)[-length:]
            return digits
        return dbc2

    def validateTOTP(self, totp, length=6, interval=30, drift=0):
        if totp is None:
            return False
        clock = time.time()
        secret = self.__password
        for d in range(-drift, drift + 1):
            candidate = self.generateTOTP(length, interval, asString=True, clock=int(clock) + (d * interval))
            #log.debug("Validate %s against candidate %s" % (totp, candidate))
            try:
                if totp == candidate:
                    return True
            except Exception,e:
                continue
        return False

    def __generateToken(self, longLiveToken = False):
        expirationTimeout = self.__tokenShortExpirationTimeout
        if longLiveToken:
            expirationTimeout = self.__tokenLongExpirationTimeout

        token = RMAuthToken(hashlib.sha224(str(uuid.uuid4())).hexdigest(), rmCurrentTimestamp() + expirationTimeout)
        self.__tokens[token.token] = token

        self.__tokensTable.addRecord(token.token, token.expiration)
        return token

    def __deleteExpiredTokens(self):
        timestamp = rmCurrentTimestamp()
        self.__tokensTable.deleteExpiredRecords(timestamp)

        if self.__tokens:
            for key, token in self.__tokens.iteritems():
                if token.expiration < timestamp:
                    self.__tokens.pop(key)

    def __deleteAccessToken(self, accessToken):
        if accessToken is None:
            return

        if accessToken in self.__tokens:
            self.__tokens.pop(accessToken)

        self.__tokensTable.deleteRecord(accessToken)

    # OpenSource Version
    def __encryptPassword(self, password):
        salt1 = ""
        salt2 = ""

        h1 = hashlib.sha512(password + salt1).hexdigest() # 128 chars
        h2 = hashlib.sha384(salt2 + h1).hexdigest() # 96 chars

        return h2

    # OpenSource Version
    def __manglePassword(self, password):
        if not password or len(password) != 96:
            return None

        tokenSize = len(password) / 16
        tokens = []

        tokens.append("3" + password[(0 * tokenSize):(1 * tokenSize)])
        tokens.append("b" + password[(15 * tokenSize):(16 * tokenSize)])

        mangle = ""

        count = 15
        while count >= 0:
            index = random.randint(0, count)
            mangle += tokens[index]

            del tokens[index]

            count -= 1

        log.debug("Password: %s" % password)
        log.debug("Mangle: %s" % mangle)

        return mangle

    def __unmanglePassword(self, mangle):
        if not mangle or len(mangle) != 112:
            return None

        tokenSize = len(mangle) / 16
        tokens = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]

        index = 0
        while index <= 15:
            token = mangle[(index * tokenSize):((index + 1) * tokenSize)]
            if token[0] == '3':
                tokens[0] = token[1:tokenSize]
            elif token[0] == 'b':
                tokens[15] = token[1:tokenSize]

            index += 1

        password = "".join(tokens)

        log.error("Mangle: %s" % mangle)
        log.error("Password: %s" % password)

        return password
