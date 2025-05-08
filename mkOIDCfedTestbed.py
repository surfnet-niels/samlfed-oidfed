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
import shutil


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

def write_file(contents, filepath, mkpath=True, overwrite=False, type='txt'):
   if mkpath:
      Path(filepath).mkdir(parents=True, exist_ok=overwrite)

   if overwrite:
      f = open(filepath, "w")
   else:
      f = open(filepath, "a")

   match type:
    case 'yaml':
         yaml.preserve_quotes = True
         yaml.dump(contents, f)
    case 'json':
         action-2
    case _:
         # assume text
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

def parseFeds(fedsJson,fedsInUse):
   RAs = {}
   
   for fedID in fedsJson.keys(): 
      if fedID in fedsInUse:
         p(fedID + " included in testbed")
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
      else:
         p(fedID + " skipped as not in use due to config")
   return RAs 

def main(argv):

   ROOTPATH='/home/debian/samlfed-oidfed'
   TESTBED_PATH = ROOTPATH + '/testbed'
   CONFIG_PATH = TESTBED_PATH + '/config/'
   INPUT_PATH = TESTBED_PATH + '/feeds/'
   OUTPUT_PATH = ROOTPATH + '/var/www/oidcfed/'
   KEYS_PATH = TESTBED_PATH + '/keys/'
   #GO_REPO_PATH = TESTBED_PATH + '/go-oidfed'
   TESTBED_BASEURL= 'oidf.lab.surf.nl'

   EDUGAIN_RA_URI = 'https://www.edugain.org'
   entityList = {}
   inputfile = None
   inputpath = INPUT_PATH
   outputpath = OUTPUT_PATH

   ENROLLLEAFS = False
   FETCHGOREPO = True

   #OIDCfed params
   baseURL = "https:///leafs.oidf.dev.eduwallet.nl/"
   metadataURLpath = ".well-known/openid-federation/"

   #
   # Fetch Gabriels go repo
   #
   #if FETCHGOREPO: 
   #   if (os.path.exists(GO_REPO_PATH)):
   #      shutil.rmtree(GO_REPO_PATH)
   #   p("Fetching Go OIDF repo into " + GO_REPO_PATH)   
   #   Repo.clone_from('git@github.com:surfnet-niels/go-oidfed.git', GO_REPO_PATH)

   #
   # Load RAs from eduGAIN
   # TODO: create way to exclude feds once they run their own infra
   #   
   #raConf = loadJSONconfig(CONFIG_PATH + 'RAs.json')
   edugainFedsURL = 'https://technical.edugain.org/api.php?action=list_feds_full'
   allFeds = getFeds(edugainFedsURL, INPUT_PATH)
   raConf = parseFeds(allFeds, ['IDEM', 'SURFCONEXT', 'HAKA'])

   # Add eduGAIN as a TA
   raConf['edugain'] = {
      'display_name': 'eduGAIN',
      'name':  'edugain',
      'reg_auth': '',
      'country_code': '',
      'md_url': [''],
      'ta_url': 'https://edugain.oidfed.lab.surf.nl'
   }

   #
   # Configure Test RPs
   # Note all other RPs will register lateron
   #
   rpConf = {
      "surf-rp": {
         "name": "SURF test RP",
         "url": "https://surf-rp." + TESTBED_BASEURL,
         "tas": ["it.idem", "edugain"]
      }, 
      "puhuri-rp": {
         "name": "Puhuri test RP",
         "url": "https://puhuri-rp." + TESTBED_BASEURL,
         "tas": ["fi.haka", "edugain"]
      }, 
      "helsinki-rp": {
         "name": "Helsinki test RP",
         "url": "https://helsinki-rp." + TESTBED_BASEURL,
         "tas": ["fi.haka", "edugain"]
      }, 
      "garr-rp": {
         "name": "GARR test RP",
         "url": "https://garr-rp." + TESTBED_BASEURL,
         "tas": ["fi.haka", "edugain"]
      }
   }

   #
   # Make sure we have all config dirs
   #
   #os.makedirs(TESTBED_PATH+'/edugain', mode=0o777, exist_ok=True)   
   os.makedirs(TESTBED_PATH+'/caddy', mode=0o777, exist_ok=True)
   for ra in raConf.keys():
      os.makedirs(TESTBED_PATH+'/' +ra+ '/data', mode=0o777, exist_ok=True)
   for rp in rpConf.keys():
      os.makedirs(TESTBED_PATH+'/' +rp+ '/data', mode=0o777, exist_ok=True)

   #
   # Build docker-compose container defenitions
   #
   tb = {
      "services": {}, 
      "networks": {"caddy": ''}
   }

   # Add edugain
   #eduGAIN = {
   #      "image": "'myoidc/oidfed-gota'",
   #      "networks": {"caddy": ''},
   #      "volumes": [TESTBED_PATH+'/edugain/data:/data'],
   #      "expose": ["8765"],
   #      "stop_grace_period": "'500ms'"
   #   }
   #tb['services']['edugain'] = eduGAIN

   # Add TAs
   for ra in raConf.keys():
      fedRA = {
         "image": "'myoidc/oidfed-gota'",
         "networks": {"caddy": ''},
         "volumes": [TESTBED_PATH+'/' +ra+ '/data:/data'],
         "expose": ["8765"],
         "stop_grace_period": "'500ms'"
      }
      tb['services'][ra] = fedRA

   # Add (test) RPs
   for rp in rpConf.keys():
      fedRP = {
         "image": "'myoidc/oidfed-gorp'",
         "networks": {"caddy": ''},
         "volumes": [
            TESTBED_PATH+'/' +rp+ '/data:/data',
            TESTBED_PATH+'/' +rp+ '/config.yaml:/config.yaml:ro'
         ],
         "expose": ["8765"],
         "stop_grace_period": "'500ms'"
      }
      tb['services'][rp] = fedRP

   # add Caddy
   tb['services']['caddy'] = {
         "image": "'caddy:latest'",
         "networks": {"caddy": ''},
         "ports": ["'80:80'", "'443:443'"],
         "volumes": [
            TESTBED_PATH + "/caddy/Caddyfile:/etc/caddy/Caddyfile",
            TESTBED_PATH + "/caddy/data:/data",
            TESTBED_PATH + "/caddy/config:/config"
         ],
         "expose": ["8765"],
         "stop_grace_period": "'500ms'"
      }

   #
   # Write config from template for all TAs
   #
   for ra in raConf.keys():
      if ra == 'edugain':
         # TODO: for edugain replace with propper YAML handling
         conf = {
            'testbed_domain': 'oidfed.lab.surf.nl'
         }
         
         with open('templates/edugain_config.yaml', 'r') as f:
            src = Template(f.read())
            result = src.substitute(conf)
            write_file(result, TESTBED_PATH+'/' +ra+ '/data/config.yaml', mkpath=False, overwrite=True)

         os.popen('cp templates/edugain_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 

      else:
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

   #
   # TODO: Write config from template for all TrustMark Issuers
   #


   #
   # TODO: Write config from template for all TEST RPs
   #
   #
   # Write config from template for all TAs
   #
   for rp in rpConf.keys():
      conf = {
         'entity_id': rpConf[rp]['url'],
         'authority': 'https://edugain.oidfed.lab.surf.nl',
         'orgname': rpConf[rp]['name'],
         'refeds_tmo_url': 'https://refeds.oidfed.lab.surf.nl',
         'edugain_member_tmi_url': 'https://edugain.oidfed.lab.surf.nl',
         'refeds_sirtfi_tmi_url': rpConf[rp]['url']
      }

      tas = ''
      for ta in rpConf[rp]['tas']:
         tas = tas + '  - entity_id: ' + raConf[ta]['ta_url']+ "\n"
      conf['tas'] = tas

      with open('templates/rp_config.yaml', 'r') as f:
         src = Template(f.read())
         result = src.substitute(conf)
         write_file(result, TESTBED_PATH+'/' +rp+ '/data/config.yaml', mkpath=False, overwrite=True)

      #os.popen('cp templates/ta_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 

   #
   # TODO: Write config from template for all TEST OPs
   #

   #
   # Build caddy configuration file to proxy all containers
   #
   caddyConf = []
   caddyConf.append('{\n     email niels.vandijk@surf.nl\n}\n')

   for ra in raConf.keys():
      caddyConf.append('\n' + ra +'.'+ TESTBED_BASEURL + ' {\n     reverse_proxy '+ra+':8765\n}  ')
   #p(''.join(caddyConf))
   write_file('\n'.join(caddyConf), TESTBED_PATH+'/caddy/Caddyfile', mkpath=False, overwrite=True)

   #Write docker compose file in tmp file
   write_file(tb, './tmp.yaml', mkpath=False, overwrite=True, type="yaml")
   # create testbed docker compose file by doing some post processing
   subprocess.run(['./mkDockerCompose.sh'])
   os.popen('mv ./docker-compose.yaml '+TESTBED_PATH+'/docker-compose.yaml') 

   sys.exit()

   fed2 = fed + '''
   
RPs = ["surf-rp", "puhuri-rp", "helsinki-rp", "garr-rp"]

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
   sys.exit()


if __name__ == "__main__":
   main(sys.argv[1:])
