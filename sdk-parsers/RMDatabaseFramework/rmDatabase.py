# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import sqlite3, os

from RMDataFramework.rmParserUserData import *
from RMDataFramework.rmParserParams import RMParserParams_adaptToSQLite, RMParserParams_convertFromSQLite
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmCommandThread import RMCommand, RMCommandThread

USE_COMMAND_THREAD__ = True


##-----------------------------------------------------------------------------------------------------
##
##
class RMTable(object):
    def __init__(self, database):
        self.database = database
        if(self.database):
            self.initialize()

    def initialize(self):
        pass

    def commit(self):
        if self.database.isOpen():
            self.database.commit()

    def __getattribute__(self, name):
        global USE_COMMAND_THREAD__
        attr = super(RMTable, self).__getattribute__(name)

        if not USE_COMMAND_THREAD__ or not attr or name.startswith("_"):
            return attr
        elif callable(attr):
            if RMCommandThread.instance.runsOnThisThread():
                return attr
            else:
                def wrapped(*args, **kwargs):
                    cmd = RMCommand(name, True)
                    cmd.command = attr
                    cmd.args = args
                    cmd.kwargs = kwargs
                    retval = RMCommandThread.instance.executeCommand(cmd)
                    return retval
                return wrapped
        else:
            return attr

##-----------------------------------------------------------------------------------------------------
##
##
class RMVersionTable(RMTable):

    CurrentVersion = 16

    def initialize(self):
        if self.database.isOpen():
            self.database.execute("CREATE TABLE IF NOT EXISTS version (version INTEGER NOT NULL DEFAULT 0)")
            self.database.commit()

            self.__insertDefaultVersion()

    def getVersion(self):
        if self.database.isOpen():
            row = self.database.execute("SELECT * FROM version").fetchone()
            if row:
                return row[0]
        return -1

    def setVersion(self, version):
        if self.database.isOpen():
            self.database.execute("UPDATE version SET version=?", (version, ))
            self.database.commit()

    def __insertDefaultVersion(self):
        row = self.database.execute("SELECT COUNT(*) FROM version").fetchone()
        if not row or row[0] == 0:
            #self.database.execute("INSERT INTO version VALUES(?)", (0, ))
            self.database.execute("INSERT INTO version VALUES(?)", (RMVersionTable.CurrentVersion, ))
            self.database.commit()

##-----------------------------------------------------------------------------------------------------
##
##
class RMDatabase:
    def __init__(self, fileName):
        self.createIfNotExists = True
        self.fileName = fileName
        self.cursor = None
        self.connection = None

        self.versionTable = None

    def open(self):
        global USE_COMMAND_THREAD__
        if USE_COMMAND_THREAD__ and not RMCommandThread.instance.runsOnThisThread():
            cmd = RMCommand("rmDatabaseOpen", True)
            cmd.command = self.__open
            return RMCommandThread.instance.executeCommand(cmd)
        return self.__open()

    def __open(self):
        if not self.createIfNotExists and not os.path.exists(self.fileName):
            return False

        self.connection = sqlite3.connect(self.fileName, detect_types=sqlite3.PARSE_DECLTYPES)
        if(self.connection):
            self.connection.row_factory = sqlite3.Row
            self.connection.text_factory = str

            self.cursor = self.connection.cursor()
            self.cursor.execute("PRAGMA foreign_keys=1")

            self.versionTable = RMVersionTable(self)

            return True
        return False

    def isOpen(self):
        return self.cursor

    def close(self):
        global USE_COMMAND_THREAD__
        if USE_COMMAND_THREAD__ and not RMCommandThread.instance.runsOnThisThread():
            cmd = RMCommand("rmDatabaseClose", True)
            cmd.command = self.__close
            return RMCommandThread.instance.executeCommand(cmd)
        return self.__close()

    def __close(self):
        if(self.connection):
            self.cursor.close()
            self.cursor = None
            self.connection.close()
            self.connection = None

    def vacuum(self):
        if not USE_COMMAND_THREAD__ or RMCommandThread.instance.runsOnThisThread():
            self.__vacuum()
        else:
            cmd = RMCommand("rmDatabaseVacuum", True)
            cmd.command = self.__vacuum
            return RMCommandThread.instance.executeCommand(cmd)

    def __vacuum(self):
        if(self.cursor):
            self.cursor.execute("VACUUM")

    def execute(self, *args):
        paramCount = len(args)
        if(self.cursor and paramCount > 0):
            if(paramCount == 1):
                self.cursor.execute(args[0])
            elif(paramCount == 2):
                self.cursor.execute(args[0], args[1])
            return self.cursor
        return None

    def executeMany(self, *args):
        paramCount = len(args)
        if(self.cursor and paramCount > 0):
            if(paramCount == 1):
                self.cursor.executemany(args[0])
            elif(paramCount == 2):
                self.cursor.executemany(args[0], args[1])

    def commit(self):
        if not USE_COMMAND_THREAD__ or RMCommandThread.instance.runsOnThisThread():
            self.__commit()
        else:
            cmd = RMCommand("rmDatabaseCommit", True)
            cmd.command = self.__commit
            return RMCommandThread.instance.executeCommand(cmd)

    def __commit(self):
        if(self.connection):
            self.connection.commit()

    def lastRowId(self):
        if(self.cursor):
            return self.cursor.lastrowid
        return None

    def registerAdapter(self, type, callable):
        sqlite3.register_adapter(type, callable)

    def registerConverter(self, typename, callable):
        sqlite3.register_converter(typename, callable)

##-----------------------------------------------------------------------------------------------------
##
##
class RMParsersDatabase(RMDatabase):
    def __init__(self, fileName):
        RMDatabase.__init__(self, fileName)

    def open(self):
        if RMDatabase.open(self):
            self.registerAdapter(RMParserUserData, RMUserData_adaptToSQLite)
            self.registerConverter("RMUserData", RMUserData_convertFromSQLite)

            self.registerAdapter(dict, RMParserParams_adaptToSQLite)
            self.registerConverter("RMParaserParams", RMParserParams_convertFromSQLite)
            return True
        return False

##-----------------------------------------------------------------------------------------------------
##
##
class RMMixerDatabase(RMDatabase):
    def __init__(self, fileName):
        RMDatabase.__init__(self, fileName)

##-----------------------------------------------------------------------------------------------------
##
##
class RMMainDatabase(RMDatabase):
    def __init__(self, fileName):
        RMDatabase.__init__(self, fileName)

##-----------------------------------------------------------------------------------------------------
##
##
class RMUserSettingsDatabase(RMDatabase):
    def __init__(self, fileName):
        RMDatabase.__init__(self, fileName)

##-----------------------------------------------------------------------------------------------------
##
##
class RMDoyDatabase(RMDatabase):
    def __init__(self, fileName):
        RMDatabase.__init__(self, fileName)

##-----------------------------------------------------------------------------------------------------
##
##
class RMSimulatorDatabase(RMDatabase):
    def __init__(self, fileName):
        RMDatabase.__init__(self, fileName)
