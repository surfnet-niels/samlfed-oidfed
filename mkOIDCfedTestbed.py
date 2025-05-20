#!/usr/bin/env python3 
#-*- coding: utf-8 -*-

import os
import time
import datetime
import sys, getopt
import json
import time
import urllib.request
from pathlib import Path
from jwcrypto import jwk, jwt
import yaml
import subprocess
from string import Template
import shutil


LOGDEBUG = True
WRITETOLOG = False

##################################################################################################################################
#
# Config and logs handling functions
#
##################################################################################################################################
def loadJSON(json_file):
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
         f.write(json.dumps(contents,sort_keys=False, indent=4, ensure_ascii=False,separators=(',', ':')))
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

class Config:
    def __init__(self):
        self.server_port = None
        self.entity_id = None
        self.authority_hints = []
        self.signing_key_file = None
        self.organization_name = None
        self.data_location = None
        self.human_readable_storage = False
        self.metadata_policy_file = None
        self.endpoints = {}
        self.trust_mark_specs = []
        self.trust_mark_owners = {}

    def from_yaml(file_path):
        config = Config()
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            if 'server_port' in data:
                config.server_port = data['server_port']
            if 'entity_id' in data:
                config.entity_id = data['entity_id']
            if 'authority_hints' in data:
                config.authority_hints = data['authority_hints']
            if 'signing_key_file' in data:
                config.signing_key_file = data['signing_key_file']
            if 'organization_name' in data:
                config.organization_name = data['organization_name']
            if 'data_location' in data:
                config.data_location = data['data_location']
            if 'human_readable_storage' in data and data['human_readable_storage'].lower() == 'true':
                config.human_readable_storage = True
            if 'metadata_policy_file' in data:
                config.metadata_policy_file = data['metadata_policy_file']
            if 'endpoints' in data:
                for endpoint_name, endpoint_data in data['endpoints'].items():
                    config.endpoints[endpoint_name] = {'path': endpoint_data['path']}
            if 'trust_mark_specs' in data:
                for trust_mark_spec in data['trust_mark_specs']:
                    spec = {}
                    if 'trust_mark_id' in trust_mark_spec:
                        spec['trust_mark_id'] = trust_mark_spec['trust_mark_id']
                    if 'lifetime' in trust_mark_spec:
                        spec['lifetime'] = trust_mark_spec['lifetime']
                    if 'ref' in trust_mark_spec:
                        spec['ref'] = trust_mark_spec['ref']
                    if 'delegation_jwt' in trust_mark_spec:
                        spec['delegation_jwt'] = trust_mark_spec['delegation_jwt']
                    if 'checker' in trust_mark_spec:
                        spec['checker'] = {'type': trust_mark_spec['checker']['type']}
                    config.trust_mark_specs.append(spec)
            if 'trust_mark_owners' in data:
                for trust_mark_id, owner_data in data['trust_mark_owners'].items():
                    owner = {}
                    if 'entity_id' in owner_data:
                        owner['entity_id'] = owner_data['entity_id']
                    if 'jwks' in owner_data:
                        owner['jwks'] = owner_data['jwks']
                    config.trust_mark_owners[trust_mark_id] = owner
            if 'trust_marks' in data:
                for trust_mark in data['trust_marks']:
                    if 'trust_mark_id' in trust_mark and 'trust_mark_issuer' in trust_mark:
                        config.trust_marks.append(trust_mark)
        return config

    def to_yaml(self, file_path):
        with open(file_path, 'w') as f:
            yaml.dump(**self.__dict__), f)

    def set_server_port(self, port):
        self.server_port = port

    def get_server_port(self):
        return self.server_port

    def set_entity_id(self, entity_id):
        self.entity_id = entity_id

    def get_entity_id(self):
        return self.entity_id

    def add_authority_hint(self, authority_hint):
        if 'authority_hints' not in self.__dict__:
            self.authority_hints = []
        self.authority_hints.append(authority_hint)

    def get_authority_hints(self):
        return self.authority_hints

   def set_server_port(self, port):
        self.server_port = port

    def get_server_port(self):
        return self.server_port

    def set_entity_id(self, entity_id):
        self.entity_id = entity_id

    def get_entity_id(self):
        return self.entity_id

    def add_authority_hint(self, authority_hint):
        if 'authority_hints' not in self.__dict__:
            self.authority_hints = []
        self.authority_hints.append(authority_hint)

    def get_authority_hints(self):
        return self.authority_hints

    def set_signing_key_file(self, file_path):
        self.signing_key_file = file_path

    def get_signing_key_file(self):
        return self.signing_key_file

    def set_organization_name(self, name):
        self.organization_name = name

    def get_organization_name(self):
        return self.organization_name

    def set_data_location(self, location):
        self.data_location = location

    def get_data_location(self):
        return self.data_location

    def set_human_readable_storage(self, storage):
        if storage.lower() == 'true':
            self.human_readable_storage = True
        else:
            self.human_readable_storage = False

    def get_human_readable_storage(self):
        return self.human_readable_storage

    def set_metadata_policy_file(self, file_path):
        self.metadata_policy_file = file_path

    def get_metadata_policy_file(self):
        return self.metadata_policy_file

    def add_endpoint(self, name, path):
        if 'endpoints' not in self.__dict__:
            self.endpoints = {}
        self.endpoints[name] = {'path': path}

    def get_endpoints(self):
        return self.endpoints

    def set_trust_mark_specs(self, specs):
        self.trust_mark_specs = specs

    def get_trust_mark_specs(self):
        return self.trust_mark_specs

    def add_trust_mark_spec(self, spec):
        if 'trust_mark_specs' not in self.__dict__:
            self.trust_mark_specs = []
        self.trust_mark_specs.append(spec)

    def set_trust_marks(self, marks):
        self.trust_marks = marks

    def get_trust_marks(self):
        return self.trust_marks

    def add_trust_mark_owner(self, trust_mark_id, entity_id, jwks):
        if 'trust_mark_owners' not in self.__dict__:
            self.trust_mark_owners = {}
        self.trust_mark_owners[trust_mark_id] = {'entity_id': entity_id, 'jwks': jwks}

    def get_trust_mark_owners(self):
        return self.trust_mark_owners



# Example usage
config = Config.from_yaml('path/to/config.yaml')
print(config.server_port)  # prints the server port from the YAML file
config.to_yaml('new/path/new_config.yaml')  # writes the config to a new file




def main(argv):

   ROOTPATH='/home/debian/samlfed-oidfed'
   TESTBED_PATH = ROOTPATH + '/testbed'
   CONFIG_PATH = TESTBED_PATH + '/config/'
   INPUT_PATH = TESTBED_PATH + '/feeds/'
   OUTPUT_PATH = ROOTPATH + '/var/www/oidcfed/'
   KEYS_PATH = TESTBED_PATH + '/keys/'
   TESTBED_BASEURL= 'oidf.lab.surf.nl'

   EDUGAIN_RA_URI = 'https://www.edugain.org'

   ENROLLLEAFS = False
   # Fetch edugain RAs from edugain technical site via URL (True) or use static file (False)?
   FETCHEDUGAINURL = True

   #
   # Load RAs from eduGAIN
   #   
   if FETCHEDUGAINURL:
      edugainFedsURL = 'https://technical.edugain.org/api.php?action=list_feds_full'
      allFeds = getFeds(edugainFedsURL, INPUT_PATH)
      raConf = parseFeds(allFeds, ['IDEM', 'SURFCONEXT', 'HAKA'])
   else:
      raConf = loadJSON(CONFIG_PATH + 'RAs.json')

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

   # Config for TMIs that are not part of TAs
   tmiConf = {
      "erasmus-plus": {
         "name": "Erasmus+ Trustmark Issuer",
         "url": "https://erasmus-plus." + TESTBED_BASEURL,
         "tas": ["edugain"]
      }
   }

   # Config for TMOs
   tmoConf = {
      "refeds": {
         "name": "REFEDs Trustmark Owner",
         "url": "https://refeds." + TESTBED_BASEURL,
         "tas": ["edugain"],
         "jwks": ""
      }, 

   }
   #
   # Make sure we have all config dirs
   # TODO: make function for this
   #os.makedirs(TESTBED_PATH+'/edugain', mode=0o777, exist_ok=True)   
   os.makedirs(TESTBED_PATH+'/caddy', mode=0o777, exist_ok=True)
   for ra in raConf.keys():
      os.makedirs(TESTBED_PATH+'/' +ra+ '/data', mode=0o777, exist_ok=True)
   for rp in rpConf.keys():
      os.makedirs(TESTBED_PATH+'/' +rp+ '/data', mode=0o777, exist_ok=True)
   for tmi in tmiConf.keys():
      os.makedirs(TESTBED_PATH+'/' +tmi+ '/data', mode=0o777, exist_ok=True)
   for tmo in tmoConf.keys():
      os.makedirs(TESTBED_PATH+'/' +tmo+ '/data', mode=0o777, exist_ok=True)

   #
   # Build docker-compose container definition
   #
   tb = {
      "services": {}, 
      "networks": {"caddy": ''}
   }

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
   # Write docker compose file in tmp file
   #
   write_file(tb, './tmp.yaml', mkpath=False, overwrite=True, type="yaml")
   # create testbed docker compose file by doing some post processing
   subprocess.run(['./mkDockerCompose.sh'])
   os.popen('mv ./docker-compose.yaml '+TESTBED_PATH+'/docker-compose.yaml') 

   # END Build docker-compose container definition

   # Build configuration for various containers

   # Add Trustmark Owners
   # TMOs are not operational infra so do not need to be in the docker compose!
   # They do need config so we can call a TMO to generate its TM delegation JWT
   # TODO: handle this with propper yaml parsing
   for tmo in tmoConf:
      conf = {
         'testbed_domain': 'oidfed.lab.surf.nl'
      }
      with open('templates/'+tmo+'_tm-delegation.yaml', 'r') as f:
         src = Template(f.read())
         result = src.substitute(conf)
         write_file(result, TESTBED_PATH+'/' +tmo+ '/data/tm-delegation.yaml', mkpath=False, overwrite=True)

      # Now run the TMO docker container to generate delegation jwt on the fly
      try:
         os.popen('docker run --rm --user "${UID}":"${GID}" -v "'+ TESTBED_PATH+'/' +tmo+'/data:/refeds" myoidc/oidfed-gota /tacli delegation --json /'+tmo+'/tm-delegation.yaml')
      except:
         p("Could not create delegation JWT for TMO " + tmo) 
      # generate JWKS
      try:
         tmoDel = loadJSON(TESTBED_PATH+'/' +tmo+'/data/tm-delegation.json')
      except:
         p("Could not parse delegation data for TMO " + tmo + ' in file ' + TESTBED_PATH+'/' +tmo+'/tm-delegation.json') 

      #pj(tmoDel)
      tmoConf[tmo]['jwks'] = tmoDel['jwks']
      tmoConf[tmo]['trust_mark_issuers'] = {}
      # loop over TMs for this TMO
      for tm in tmoDel['trust_marks']:
         p(tm["trust_mark_id"])
         #p(tm["trust_mark_issuers"])
         for tmi in tm["trust_mark_issuers"]:
            tmoConf[tmo]['trust_mark_issuers'][tmi['entity_id']] = tmi['delegation_jwt']

      # Put JWKS and delegation JWT in config so we can add it to the TA config
      pj(tmoConf)


   # Add Trust Mark Issuers
   # This are stand alone TMIs. Some TAs may also be TMIs, that is part of TA config
   # Some TMIs may be issuing delegated TMIs for a given TMO
   for tmi in tmiConf.keys():
      fedTMI = {
         "image": "'myoidc/oidfed-gota'",
         "networks": {"caddy": ''},
         "volumes": [TESTBED_PATH+'/' +tmi+ '/data:/data'],
         "expose": ["8765"],
         "stop_grace_period": "'500ms'"
      }
      tb['services'][tmi] = fedTMI
      os.popen('cp templates/edugain_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 

   #
   # Write config from template for all TAs
   #
   for ra in raConf.keys():
      if ra == 'edugain':
         # TODO: for edugain replace with proper YAML handling
         # TODO: proper TMI handling
         conf = {
            'testbed_domain': 'oidfed.lab.surf.nl',
            'refeds_tmo_url': 'https://refeds.oidfed.lab.surf.nl',
            'refeds_jwks': tmoConf['refeds']['jwks']
         }
         
         with open('templates/edugain_config.yaml', 'r') as f:
            src = Template(f.read())
            result = src.substitute(conf)
            write_file(result, TESTBED_PATH+'/' +ra+ '/data/config.yaml', mkpath=False, overwrite=True)

         os.popen('cp templates/edugain_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 

      else:
         # TODO: proper TMI handling
         conf = {
            'entity_id': raConf[ra]['ta_url'],
            'ta': 'https://edugain.oidfed.lab.surf.nl',
            'orgname': raConf[ra]['name'],
            'refeds_tmo_url': 'https://refeds.oidfed.lab.surf.nl',
            'refeds_jwks': tmoConf['refeds']['jwks'],
            'edugain_member_tmi_url': 'https://edugain.oidfed.lab.surf.nl',
            'refeds_sirtfi_tmi_url': raConf[ra]['ta_url'],
            'refeds_delegation_jwt': tmoConf['refeds']['trust_mark_issuers'][raConf[ra]['ta_url']]
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

if __name__ == "__main__":
   main(sys.argv[1:])
