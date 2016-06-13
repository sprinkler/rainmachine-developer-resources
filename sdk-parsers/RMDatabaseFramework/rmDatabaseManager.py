# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import os

from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmCommandThread import RMCommand, RMCommandThread
from RMDatabaseFramework.rmDatabase import *

class RMDatabaseManager:
    #-----------------------------------------------------------------------------------------------
    #
    #
    #
    def __init__(self):
        self.mainDatabasePath = None
        self.parserDatabasePath = None
        self.mixerDatabasePath = None
        self.settingsDatabasePath = None
        self.doyDatabasePath = None
        self.simulatorDatabasePath = None

        self.mainDatabase = None
        self.parserDatabase = None
        self.mixerDatabase = None
        self.settingsDatabase = None
        self.doyDatabase = None
        self.simulatorDatabase = None

    #-----------------------------------------------------------------------------------------------
    #
    #
    #
    def initialize(self, databasePath):
        self.mainDatabasePath = os.path.join(databasePath, 'rainmachine-main.sqlite')
        self.parserDatabasePath = os.path.join(databasePath, 'rainmachine-parser.sqlite')
        self.mixerDatabasePath = os.path.join(databasePath, 'rainmachine-mixer.sqlite')
        self.settingsDatabasePath = os.path.join(databasePath, 'rainmachine-settings.sqlite')
        self.doyDatabasePath = os.path.join(databasePath, 'rainmachine-doy.sqlite')
        self.simulatorDatabasePath = os.path.join(databasePath, 'rainmachine-simulator.sqlite')

        cmd = RMCommand("RMDatabaseManagerOpen", True)
        cmd.command = self.__openDatabases
        RMCommandThread.instance.executeCommand(cmd)

    def uninitialize(self):
        cmd = RMCommand("RMDatabaseManagerClose", True)
        cmd.command = self.__openDatabases
        RMCommandThread.instance.executeCommand(cmd)

    #-----------------------------------------------------------------------------------------------
    #
    #
    #
    def __openDatabases(self):
        self.mainDatabase = RMMainDatabase(self.mainDatabasePath)
        self.mainDatabase.open()

        self.parserDatabase = RMParsersDatabase(self.parserDatabasePath)
        self.parserDatabase.open()

        self.mixerDatabase = RMMixerDatabase(self.mixerDatabasePath)
        self.mixerDatabase.open()

        self.settingsDatabase = RMUserSettingsDatabase(self.settingsDatabasePath)
        self.settingsDatabase.open()

        self.doyDatabase = RMDoyDatabase(self.doyDatabasePath)
        self.doyDatabase.open()

        self.simulatorDatabase = RMSimulatorDatabase(self.simulatorDatabasePath)
        self.simulatorDatabase.open()

    def __closeDatabases(self):
        if self.mainDatabase:
            self.mainDatabase.close()
            self.mainDatabase = None

        if self.parserDatabase:
            self.parserDatabase.close()
            self.parserDatabase = None

        if self.mixerDatabase:
            self.mixerDatabase.close()
            self.mixerDatabase = None

        if self.settingsDatabase:
            self.settingsDatabase.close()
            self.settingsDatabase = None

        if self.mainDatabase:
            self.mainDatabase.close()
            self.mainDatabase = None

        if self.doyDatabase:
            self.doyDatabase.close()
            self.doyDatabase = None

        if self.simulatorDatabase:
            self.simulatorDatabase.close()
            self.simulatorDatabase = None

#-----------------------------------------------------------------------------------------------
#
#
#
globalDbManager = RMDatabaseManager()
