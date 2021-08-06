# RainMachine Community Weather Services

This repository holds the RainMachine weather services (parsers) developed by community. While RainMachine takes steps to ensure that these weather services
run correctly and aren't malicios, we can't take any responsability for the use of these weather services.

## RainMachine Weather Engine

RainMachine Weather Engine can run multiple weather services and aggregate their results. The minimum aggregation interval is 1h. This is done automatically
by RainMachine Mixer which takes the readings from all weather services and aggregates for hourly/daily values that will be used by RainMachine to compute irrigation needs.
[RainMachine Weather Engine](https://support.rainmachine.com/hc/en-us/articles/360011755813-RainMachine-Weather-Engine)

## How to create a new weather service

Please read: [Developing Weather Services](https://support.rainmachine.com/hc/en-us/articles/228620727-How-to-integrate-RainMachine-with-different-weather-forecast-services)

## How to submit a new weather service

Kindly send a pull request against this repository. We will verify the pull request and merge it. After that we will add a new entry into version-metadata.json file.

## Updates

Everytime a weather service is modified (that has been included in version-metadata.json) a github action will run and increment the version in the metadata file.

## Limits

1. *Limit the amount of logging.* Since RainMachine uses flash storage with a limited write count make sure your weather service doesn't log too much data. In general this should be less that 1KB per run.
2. *Limit the size.* Weather Services over 16KB can't be installed over the cloud but can be installed by directly connecting to RainMachine via local network with web or mobile) apps.
3. *Limit the resources used*. Make sure your Weather Service doesn't hog CPU or uses more than 1MB of memory otherwise RainMachine might automatically restart if it gets stuck.
4. *Limit the network utilisation*. Make sure you don't trasfer a lot of data each run should be under 200KB of data transfered.
