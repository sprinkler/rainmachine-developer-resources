# Description
   RainMachine SDK allows developers to extend the functionality of RainMachine by creating custom pieces of code that will run directly on device itself along with the existing RainMachine software. While RainMachine API allows developer to control the device through a standard set of REST calls the SDK can be used to provide new functionality. 
   At this moment the focus of the SDK is the creation of Weather Services (called parsers) but can be used for other functionality like automated restrictions, automatic program scheduling etc. The so called parsers, run periodically on device using the parserInterval specified on the source code (minimum 60 seconds), and have access to the inner workings of RainMachine so their possibilities are endless. 

Programming using the SDK is done in Python. The easiest way to use the SDK is by installing the PyCharm IDE.
This guide presents the steps for setting up the development environment in PyCharm.

# Download the RainMachine SDK 

```
git clone https://github.com/sprinkler/rainmachine-developer-resources.git
```

Alternativelly you can download a zip archive:

```
wget https://github.com/sprinkler/rainmachine-developer-resources/archive/master.zip
unzip master.zip
```

# Download and install Pycharm
 
   PyCharm is a cross-platform Integrated Development Environment (IDE) used for programming in Python. It provides code analysis, a graphical debugger, an integrated unit tester, integration with version control systems. It works on Windows, Mac OS X and Linux. You can download the free community edition here: https://www.jetbrains.com/pycharm/download/

## Select project folder

   Open PyCharm and select Open to choose the folder sdk-parser from where the rainmachine-developer-resources have been cloned/unpacked.

![alt text](https://support.rainmachine.com/hc/en-us/article_attachments/213223948/Pycharm-select-project.png "Select folder")

## Edit or create a new parser

Parsers reside in RMParserFramework/parsers. All *.py files in this folder will be automatically loaded when project is run.

![alt text](https://support.rainmachine.com/hc/en-us/article_attachments/213447127/Pycharm-open-parser.png "New parser")

To start, you can either edit existing example-parser.py or create a simple file named test-parser.py with the following content:
```
from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging

class ExampleParser(RMParser):
    parserName = "My Example Parser"
    parserDescription = "Example parser for developers"
    parserInterval = 3600 # delay between runs in seconds

    def perform(self):
        log.info("Hello World")
```

# Quick run and test

If you just need to quickly test the parser you can add these lines at the bottom of the parser source code:
```
if __name__ == "__main__":
    p = ExampleParser()
    p.perform()
```

Right clicking on parser opened source code, you can select *Run 'test-parser'*, the parser will be executed and you should see in output console something similar to:
```
/System/Library/Frameworks/Python.framework/Versions/2.7/bin/python /Users/Development/rainmachine/RMParserFramework/parsers/test-parser.py
2016-06-18 15:48:00,233 - INFO  - rmParser:69 - *** Registering parser My Example Parser with interval 3600
2016-06-18 15:48:00,234 - INFO  - test-parser:10 - Hello World

Process finished with exit code 0
```

# Edit Run configuration

   If you want to test the automatic periodic execution you must edit run configurations, from *Run - Edit Configurations...* menu option, as shown below:

![alt text](https://support.rainmachine.com/hc/en-us/article_attachments/213223968/Pycharm-run-configuration.png)

   The parameters are separated by comma and have the following format: 
   ```
   <RainMachine Name>,<TimeZone String>,<Latitude>,<Longitude>,<Elevation>
   ``` 
Working directory must be set to the sdk-parser folder.

![alt text](https://support.rainmachine.com/hc/en-us/article_attachments/213224028/800px-Pycharm-run-configuration-2.png)

# Parsers Database

   Parsers save their data on a sqlite database which is located in DB/<RainMachine Name> folder. 
This folder is automatically created at first run if doesn't exists.
This data can be browsed with a sqlite browser: http://sqlitebrowser.org/ by viewing the parserData table.

![alt text](https://support.rainmachine.com/hc/en-us/article_attachments/213224008/Parser-db-path.png)

# Run project

![alt text](https://support.rainmachine.com/hc/en-us/article_attachments/213447187/Pycharm-run.png)

   Press the Run button to execute the project. After initial setup all enabled parsers will be run every minute.
This behavior can be changed by removing **forceRunParser = True** from the rmParserManager.py line 84.
Removing this flag parsers will be executed by their parserInterval defined for each parser, which is how they are run on device.

# Further reading

https://support.rainmachine.com/hc/en-us/articles/228620727-How-to-integrate-RainMachine-with-different-weather-forecast-services

