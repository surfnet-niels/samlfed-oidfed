#!/usr/bin/env python3 
#-*- coding: utf-8 -*-

import xml.etree.cElementTree as ET
from operator import itemgetter
from collections import OrderedDict

import os
import time
import datetime
import sys, getopt
import json
import hashlib
import time
import urllib.request
from pathlib import Path
from jwcrypto import jwk, jwt
import yaml
import subprocess
from string import Template
from git import Repo


LOGDEBUG = True
WRITETOLOG = False

##################################################################################################################################
#
# Config and logs handling functions
#
##################################################################################################################################
def loadJSONconfig(json_file):
   with open(json_file) as json_file:
     return json.load(json_file)

def p(message, writetolog=WRITETOLOG):
   if writetolog:
      write_log(message)
   else:
      print(message)
    
def pj(the_json, writetolog=WRITETOLOG):
    p(json.dumps(the_json, indent=4, sort_keys=False), writetolog)

def write_log(message):
   datestamp = (datetime.datetime.now()).strftime("%Y-%m-%d")
   timestamp = (datetime.datetime.now()).strftime("%Y-%m-%d %X")
   f = open("./logs/" + datestamp + "_apistatus.log", "a")
   f.write(timestamp +" "+ message+"\n")
   f.close()

def write_file(contents, filepath, mkpath=True, overwrite=False):
   if mkpath:
      Path(filepath).mkdir(parents=True, exist_ok=overwrite)

   if overwrite:
      f = open(filepath, "w")
   else:
      f = open(filepath, "a")

   f.write(contents+"\n")
   f.close()

def is_file_older_than_x_days(file, days=1): 
    file_time = os.path.getmtime(file) 
    # Check against 24 hours 
    if (time.time() - file_time) / 3600 > 24*days: 
        return True
    else: 
        return False

def fetchFile(url, file_path, overwrite=True):
  Path(os.path.dirname(file_path)).mkdir(parents=True, exist_ok=overwrite)
  try:
    urllib.request.urlretrieve(url, file_path)
    return True
  except:
    p("ERROR: Could not download URL: " + url, LOGDEBUG)
    return False

def getFeds(ulr, input_path):
  json_file = input_path + 'allfeds.json'
  fetchFile(ulr, json_file)
  with open(json_file) as json_file:
     return json.load(json_file)

def parseFeds(fedsJson):
   RAs = {}
   
   for fedID in fedsJson.keys(): 
      if fedsJson[fedID]['status'] == "6":
         if "countries" in fedsJson[fedID]:
            for i in range(0,len(fedsJson[fedID].get('countries'))): 
               fedID_country = ''.join(fedsJson[fedID].get('country_code')[i].lower()) +'.'+fedID.lower() 
               thisFedData = {'display_name': fedsJson[fedID]['name'] + ' (' + ''.join(fedsJson[fedID].get('countries')[i]) +')',
                  'name':  ''.join(fedsJson[fedID].get('country_code')[i].lower())+ '_' + fedsJson[fedID]['name'].lower(),
                  'reg_auth': fedsJson[fedID]['reg_auth'],
                  'country_code': ''.join(fedsJson[fedID].get('country_code')[i]),
                  'md_url': [fedsJson[fedID]['metadata_url']],
                  'ta_url': 'https://'+''.join(fedsJson[fedID].get('country_code')[i])+'.'+fedID.lower()+ '.oidfed.lab.surf.nl'}

               RAs[fedID_country] = thisFedData
   return RAs 

def main(argv):

   ROOTPATH='/tmp/go-oidfed/examples/edugain-pilot'
   TESTBED_PATH = ROOTPATH + '/testbed'
   CONFIG_PATH = ROOTPATH + '/testbed/config/'
   INPUT_PATH = ROOTPATH + '/testbed/feeds/'
   OUTPUT_PATH = ROOTPATH + '/var/www/oidcfed/'
   KEYS_PATH = ROOTPATH + '/testbed/keys/'

   EDUGAIN_RA_URI = 'https://www.edugain.org'
   entityList = {}
   inputfile = None
   inputpath = INPUT_PATH
   outputpath = OUTPUT_PATH

   ENROLLLEAFS = False

   #OIDCfed params
   baseURL = "https:///leafs.oidf.dev.eduwallet.nl/"
   metadataURLpath = ".well-known/openid-federation/"

   # Fetch Gabriels go repo 
   Repo.clone_from('git@github.com:surfnet-niels/go-oidfed.git', '/tmp/go-oidfed')

   # First load RA config
   #raConf = loadJSONconfig(CONFIG_PATH + 'RAs.json')
   edugainFedsURL = 'https://technical.edugain.org/api.php?action=list_feds_full'
   allFeds = getFeds(edugainFedsURL, INPUT_PATH)
   raConf = parseFeds(allFeds)

   # create a docker compose file contents header
   fed = {
      "services": {}, 
      "networks": {"caddy": ''}
   }

   for ra in raConf.keys():
      #build docker file conatinaer defenitions
      fedRA = {
         "image": "'myoidc/oidfed-gota'",
         "networks": {"caddy": ''},
         "volumes": [TESTBED_PATH+'/' +ra+ ':/data'],
         "expose": ["8765"],
         "stop_grace_period": "'500ms'"
      }
      fed['services'][ra] = fedRA

   #Write docker file in tmp file
   with open('./tmp.yaml', 'w') as f:
      yaml.preserve_quotes = True
      yaml.dump(fed, f)

   # create testbed init file
   subprocess.run(['./mkDockerCompose.sh'])
   os.popen('mv ./docker-compose.yaml '+TESTBED_PATH+'/docker-compose.yaml') 
   
   # make sure we have all config dirs
   for ra in raConf.keys():
      os.makedirs(TESTBED_PATH+'/' +ra+ '/data', mode=0o777, exist_ok=True)

   for ra in raConf.keys():
      conf = {
         'entity_id': raConf[ra]['ta_url'],
         'ta': 'https://edugain.oidfed.lab.surf.nl',
         'orgname': raConf[ra]['name'],
         'refeds_tmo_url': 'https://refeds.oidfed.lab.surf.nl',
         'edugain_member_tmi_url': 'https://edugain.oidfed.lab.surf.nl',
         'refeds_sirtfi_tmi_url': raConf[ra]['ta_url']
      }

      with open('templates/ta_config.yaml', 'r') as f:
         src = Template(f.read())
         result = src.substitute(conf)
         write_file(result, TESTBED_PATH+'/' +ra+ '/data/config.yaml', mkpath=False, overwrite=True)

   
      os.popen('cp templates/ta_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 


   # replace quotes in temp file and write as docker compose file
   # set right permissions on files
   #subprocess.run(["./mktestbed.sh"]) 
  
   sys.exit()

   fed2 = fed + '''
   
   surf-rp:
      image: myoidc/oidfed-gorp
      volumes:
      - ./surf-rp/config.yaml:/config.yaml:ro
      - ./surf-rp:/data
      networks:
      caddy:
      stop_grace_period: 500ms
   puhuri-rp:
      image: myoidc/oidfed-gorp
      volumes:
      - ./puhuri-rp/config.yaml:/config.yaml:ro
      - ./puhuri-rp:/data
      networks:
      caddy:
      stop_grace_period: 500ms
   helsinki-rp:
      image: myoidc/oidfed-gorp
      volumes:
      - ./helsinki-rp/config.yaml:/config.yaml:ro
      - ./helsinki-rp:/data
      networks:
      caddy:
      stop_grace_period: 500ms
   garr-rp:
      image: myoidc/oidfed-gorp
      volumes:
      - ./garr-rp/config.yaml:/config.yaml:ro
      - ./garr-rp:/data
      networks:
      caddy:
      stop_grace_period: 500ms


   caddy:
      image: caddy:latest
      container_name: caddy
      ports:
      - "80:80"
      - "443:443"
      volumes:
      - ./caddy/Caddyfile:/etc/caddy/Caddyfile
      - ./caddy/data:/data
      - ./caddy/config:/config
      networks:
      - caddy

   networks:
      caddy:
   '''
   #with open('data.yaml', 'w') as f:
   #   yaml.dump(d, f)
   sys.exit()


if __name__ == "__main__":
   main(sys.argv[1:])
