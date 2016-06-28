# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>


from API4Client.rmAPIClient import *

client = RMAPIClient(host="127.0.0.1", port="18080")

print client.zones.get()
print client.programs.get()

