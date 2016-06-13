# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import ftplib
import os, sys

sys.path.insert(0, ".")

from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp


class RMDiagUpload:

    STATUS_CONNECT_ERROR = -2
    STATUS_UPLOAD_ERROR = -1
    STATUS_IDLE = 0
    STATUS_CONNECTING = 1
    STATUS_UPLOADING = 2

    def __init__(self):
        self.status = RMDiagUpload.STATUS_IDLE

        self.timeout = 15

        self.ftpHost = "ftp.rainmachine.com"
        self.ftpPort = 21
        self.ftpUserName = "raindiag"
        self.ftpPassword = "476f537570706f7274313321"

        # relative to globalSettings.databasePath
        self.fileList = [
            "log/rainmachine.log",
            "log/rainmachine.log.1.gz",
            "/tmp/simulator-volatile.log", # Latest simulator log on tmpfs we don't send the persistent log/simulator.log
            "rainmachine-doy.sqlite",
            "rainmachine-main.sqlite",
            "rainmachine-mixer.sqlite",
            "rainmachine-parser.sqlite",
            "rainmachine-settings.sqlite",
            "rainmachine-simulator.sqlite",
            os.path.join(globalSettings.cloud._logPath, "cloud-client.log")
        ]

        self.__ftp = ftplib.FTP()

    def uploadDiag(self):

        localPath = globalSettings.databasePath
        remotePath = self.__getUploadFolderName()
        filesUploaded = 0
        try:
            self.__connect()
            self.__ftp.mkd(remotePath)
            self.__ftp.cwd(remotePath)

            # Application files
            for file in self.fileList:
                try:
                    self.status = RMDiagUpload.STATUS_UPLOADING
                    if os.path.isabs(file):
                        self.__upload(None, file)
                    else:
                        self.__upload(localPath, file)

                    filesUploaded += 1
                except Exception, e:
                    log.error("uploadDiag: File: %s : %s" % (file, e))

            if filesUploaded > 0:   # rainmachine.log.1.gz might not had been created
                self.status = RMDiagUpload.STATUS_IDLE
            else:
                self.status = RMDiagUpload.STATUS_UPLOAD_ERROR

            self.__ftp.quit()

        except Exception, e:
            log.error("Couldn't start upload: %s", e)
            self.status = RMDiagUpload.STATUS_CONNECT_ERROR

    def __connect(self):
        self.status = RMDiagUpload.STATUS_CONNECTING
        self.__ftp.connect(self.ftpHost, self.ftpPort, self.timeout)
        self.__ftp.login(self.ftpUserName, self.ftpPassword.decode("hex"))
        log.debug("Connected to %s" % self.ftpHost)

    def __upload(self, localPath, file):
        with open(os.path.join(localPath, file), "rb") as f:
            log.debug("Uploading file: %s" % file)

            extraRemotePath = os.path.split(file)[0]

            if extraRemotePath:
                if os.path.isabs(extraRemotePath):
                    extraRemotePath = extraRemotePath.lstrip("/")
                    file = file.lstrip("/")
                try:
                    self.__ftp.mkd(extraRemotePath)
                except Exception, e:
                    log.debug("Folder %s/ creation failed: %s" % (extraRemotePath, e))

            self.__ftp.storbinary("STOR " + file, f)

    def __getUploadFolderName(self):
        return globalSettings.netName + "-SPK-" + str(globalSettings.hardwareVersion) + "-" \
               + globalWIFI.wifiInterface.macAddress + "-" + str(rmCurrentTimestamp())

# -----------------------------------------------------------------------------------------------------------
# Main Test Unit
#
if __name__ == "__main__":
    globalSettings.parseSysArguments()
    globalWIFI.detect()
    lu = RMDiagUpload()
    lu.uploadDiag()
    log.info("Status is: %s" % lu.status)
