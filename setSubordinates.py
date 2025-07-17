#!/usr/bin/env python3 
#-*- coding: utf-8 -*-

import json
import sys
import subprocess

subordinatesFile = sys.argv[1] 

def loadJSON(json_file):
   with open(json_file) as json_file:
     return json.load(json_file)

data = loadJSON(subordinatesFile)

for ta in data.keys():
    print(ta)
    for sub in data[ta]:
       print(sub)
       subprocess.run("docker exec testbed-" +ta+ "-1 /tacli -c /data/config.yaml subordinates add " + sub, shell=True)
    print("--") 
