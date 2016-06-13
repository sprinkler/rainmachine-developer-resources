# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import os, sys, imp

from RMUtilsFramework.rmLogging import log
from RMDatabaseFramework.rmDatabase import RMVersionTable
from RMDatabaseFramework.rmDatabaseManager import globalDbManager
from RMUtilsFramework.rmCommandThread import RMCommand, RMCommandThread

#----------------------------------------------------------------------------------
#
#
class RMDatabaseUpdate:

    #------------------------------------------------------------------------------
    #
    #
    @staticmethod
    def update():
        updateVersion, dbVersion = RMDatabaseUpdate.getVersions()

        if updateVersion < dbVersion:
            # Newer DB version on and old software
            return False

        if updateVersion == dbVersion:
            # Everything is up to date.
            return True

        cmd = RMCommand("db-update", True)
        cmd.command = RMDatabaseUpdate.__doUpdate
        cmd.args = (dbVersion, updateVersion)
        return RMCommandThread.instance.executeCommand(cmd)

    #------------------------------------------------------------------------------
    #
    #
    @staticmethod
    def getVersions():
        return RMVersionTable.CurrentVersion, globalDbManager.mainDatabase.versionTable.getVersion()

    #------------------------------------------------------------------------------
    #
    #
    @staticmethod
    def __doUpdate(fromVersion, toVersion):

        updateScriptsDir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dbUpdateScripts"))
        if not os.path.exists(updateScriptsDir):
            return False

        for version in range(fromVersion + 1, toVersion + 1):
            moduleName = "updateV%d" % (version)
            scriptName = moduleName + ".py"
            scriptPath = os.path.join(updateScriptsDir, scriptName)
            compiled = False

            if not os.path.exists(scriptPath):
                scriptName = moduleName + ".pyc"
                scriptPath = os.path.join(updateScriptsDir, scriptName)
                compiled = True

            log.info("... applying database upgrade: %s" % scriptPath)

            if not os.path.exists(scriptPath):
                return False

            success = False
            try:
                if compiled:
                    module = imp.load_compiled(moduleName, scriptPath)
                else:
                    module = imp.load_source(moduleName, scriptPath)

                try:
                    success = module.performUpdate()
                except Exception, e:
                    log.error(e)

                del sys.modules[moduleName]

            except Exception, e:
                log.error(e)
                return False

        return True
