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

class tmo_config:
    def __init__(self):
        self.trust_mark_owner = None
        self.trust_marks = []

    def from_yaml(file_path):
        config = tmo_config()
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            if 'trust_mark_owner' in data:
                config.trust_mark_owner = data['trust_mark_owner']
            if 'trust_marks' in data:
                for trust_mark in data['trust_marks']:
                    tm = {}
                    if 'trust_mark_id' in trust_mark:
                        tm['trust_mark_id'] = trust_mark['trust_mark_id']
                    if 'delegation_lifetime' in trust_mark:
                        tm['delegation_lifetime'] = trust_mark['delegation_lifetime']
                    if 'logo_uri' in trust_mark:
                        tm['logo_uri'] = trust_mark['logo_uri']                        
                    if 'ref' in trust_mark:
                        tm['ref'] = trust_mark['ref']
                    if 'trust_mark_issuers' in trust_mark:
                        tm['trust_mark_issuers'] = trust_mark['trust_mark_issuers']

        return config
    
    def to_yaml(self, file_path):
        with open(file_path, 'w') as f:
            yaml.dump((self.__dict__), f)

    def get_trust_mark_owner(self):
        return self.trust_mark_owner

    def set_trust_mark_owner(self, trust_mark_owner):
        self.trust_mark_owner = trust_mark_owner

    def add_trust_mark(self, trust_mark_id, trust_mark_issuers, delegation_lifetime=86400, logo_uri=None, ref=None):
        tm = {}
        tm['trust_mark_id'] = trust_mark_id
        tm['delegation_lifetime'] = delegation_lifetime
        tm['logo_uri'] = logo_uri                        
        tm['ref'] = ref
        tm['trust_mark_issuers'] =[]
        for tmi in trust_mark_issuers:  
            tm['trust_mark_issuers'].append({"entity_id": tmi}) 
        self.trust_marks.append(tm)

class trustmark:
    def __init__(self):
        self.trust_mark_id = None
        self.delegation_lifetime = None
        self.ref = []
        self.logo_uri=None
        self.trust_mark_issuers = None

    def set_delegation_lifetime(self, delegation_lifetime):
        self.delegation_lifetime = delegation_lifetime     

    def set_ref(self, ref):
        self.ref = ref

    def set_logo_uri(self, logo_uri):
        self.logo_uri = logo_uri

    def add_trust_mark_issuers(self, entity_id):
        self.trust_mark_issuers = []
        self.trust_mark_issuers.append({"entityid": entity_id})

class ta_config:
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
        self.trust_marks = []
        self.trust_mark_owners = {}

    def from_yaml(file_path):
        config = ta_config()
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
            if 'human_readable_storage' in data:
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
            yaml.dump((self.__dict__), f)

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

    def add_trust_mark_specs(self, trust_mark_id, ref, delegation_jwt, lifetime=86400, checker_type="none"):
        if 'trust_mark_specs' not in self.__dict__:
            self.trust_mark_specs = []
        self.trust_mark_specs.append({'trust_mark_id': trust_mark_id, 
                                      "lifetime": lifetime,
                                      'ref': ref,
                                      'delegation_jwt': delegation_jwt,
                                      "checker": {"type" : checker_type} })   

    def get_trust_mark_specs(self):
        return self.trust_mark_specs

    def add_trust_mark(self, trust_mark_id, trust_mark_issuer):
        if 'trust_marks' not in self.__dict__:
            self.trust_marks = []
        self.trust_marks.append({'trust_mark_id': trust_mark_id, 'trust_mark_issuer': trust_mark_issuer})   

    def get_trust_marks(self):
        return self.trust_marks

    def add_trust_mark_owner(self, trust_mark_id, entity_id, jwks):
        if 'trust_mark_owners' not in self.__dict__:
            self.trust_mark_owners = {}
        self.trust_mark_owners[trust_mark_id] = {'entity_id': entity_id, 'jwks': jwks}

    def get_trust_mark_owners(self):
        return self.trust_mark_owners

def main(argv):

    ROOTPATH=os.getcwd()
    TESTBED_PATH = ROOTPATH + '/testbed'
    CONFIG_PATH = TESTBED_PATH + '/config/'
    INPUT_PATH = ROOTPATH + '/feeds/'
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
    else:
        allFeds = loadJSON(INPUT_PATH + 'allfeds.json')

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

    # Config for TMIs that are not part of TAs
    tmiConf = {
        "edugain": {
            "name": "eduGAIN Membership Trustmark Issuer",
            "url": "https://erasmus-plus." + TESTBED_BASEURL,
            "tas": ["edugain"],
            "trust_mark_id": "https://edugain.org/member",
            "logo_uri": "https://edugain.org/wp-content/uploads/2018/02/eduGAIN.jpg",
            "ref": "",
        },
        "erasmus-plus": {
            "name": "Erasmus+ Trustmark Issuer",
            "url": "https://erasmus-plus." + TESTBED_BASEURL,
            "tas": ["edugain"],
            "trust_mark_id": "",
            "logo_uri": "",
            "ref": "",
        }
    }

    # Config for TMOs
    tmoConf = {
        "refeds": {
            "name": "REFEDs Trustmark Owner",
            "url": "https://refeds." + TESTBED_BASEURL,
            "tas": ["edugain"],
            "jwks": "",
            "trust_mark_id": "https://refeds.org/sirtfi",
            "ref": "https://refeds.org/wp-content/uploads/2022/08/Sirtfi-v2.pdf",
            "trust_mark_issuers": [
                "https://nl.surfconext"+ TESTBED_BASEURL,
                "https://it.idem"+ TESTBED_BASEURL,
                "https://us.incommon"+ TESTBED_BASEURL,
                "https://fi.haka"+ TESTBED_BASEURL,
                "https://se.swamid"+ TESTBED_BASEURL
            ]
        }, 

    }
    #
    # Make sure we have all config dirs
    # TODO: make function for this
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
    for this_tmo in tmoConf:
        # read the TMO config template
        tmo = tmo_config.from_yaml('templates/tmo_config.yaml')
        tmo.set_trust_mark_owner(trust_mark_owner=tmoConf[this_tmo]["url"])
        tmo.add_trust_mark(trust_mark_id=tmoConf[this_tmo]["trust_mark_id"], 
                           trust_mark_issuers=tmoConf[this_tmo]["trust_mark_issuers"]
                           )
        tmo.to_yaml(TESTBED_PATH+'/' +this_tmo+ '/data/tm-delegation.yaml')

        # Now run the TMO docker container to generate delegation jwt on the fly
        docker_cmd = 'docker run --rm --user "1000":"1000" -v "'+ TESTBED_PATH+'/' +this_tmo+'/data:/refeds" myoidc/oidfed-gota /tacli delegation --json /'+this_tmo+'/tm-delegation.yaml' 
        try:
            os.popen(docker_cmd)
        except:
            p("Could not create delegation JWT for TMO " + this_tmo + "!\n Tried to run: \n " + docker_cmd)
        
        # the docker might be a bit slow so wait untill the file has been created
        while not os.path.exists(TESTBED_PATH+'/' +this_tmo+'/data/tm-delegation.json'):
            time.sleep(1)
        else:
            # generate JWKS
            try:
                tmoDel = loadJSON(TESTBED_PATH+'/' +this_tmo+'/data/tm-delegation.json')
            except:
                p("Could not parse delegation data for TMO " + this_tmo + ' in file ' + TESTBED_PATH+'/' +this_tmo+'/tm-delegation.json') 

        #pj(tmoDel)
        tmoConf[this_tmo]['jwks'] = tmoDel['jwks']
        tmoConf[this_tmo]['trust_mark_issuers'] = {}
        # loop over TMs for this TMO
        for tm in tmoDel['trust_marks']:
            for tmi in tm["trust_mark_issuers"]:
                tmoConf[this_tmo]['trust_mark_issuers'][tmi['entity_id']] = tmi['delegation_jwt']

        # Put JWKS and delegation JWT in config so we can add it to the TA config
        #pj(tmoConf)


    # Add Trust Mark Issuers
    # These are stand alone TMIs. Some TAs may also be TMIs, that is part of TA config
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
        # read the TA config template
        ta = ta_config.from_yaml('templates/ta_config.yaml')
        #print(ta.get_endpoints())  # prints the server port from the YAML file
        
        #entity_id
        ta.set_entity_id(raConf[ra]["ta_url"])
        #organization_name
        ta.set_organization_name(raConf[ra]["display_name"])

        # Update values as needed
        if ra == 'edugain':
            # TODO: for edugain replace with proper YAML handling
            # TODO: proper TMI handling
            # Add REFEDs as SIRTFI trustmark owner

            ta.add_trust_mark_owner(trust_mark_id="https://refeds.org/sirtfi", entity_id="https://refeds.oidfed.lab.surf.nl",jwks=tmoConf['refeds']['jwks'])


            # Copy over edugain policy template 
            os.popen('cp templates/edugain_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 

        else:
            # for now all Tas have eduGAIN as the parent
            ta.add_authority_hint(raConf["edugain"]['ta_url'])

            # Add TMOs to the TAs
            for tmo in tmoConf:
                if ta.get_entity_id() in tmoConf[tmo]["trust_mark_issuers"]:
                    p("Found TMI " + tmo + " I must issue for")
                #p(ta.get_entity_id())
                #p(tmoConf[tmo]["trust_mark_issuers"].keys())

                    # Add trustmark owner
                    ta.add_trust_mark_owner(trust_mark_id=tmoConf[tmo]["trust_mark_id"], 
                                            entity_id=tmoConf[tmo]["url"],
                                            jwks=tmoConf[tmo]['jwks'])

                    # Add TrustMark Spec so this TA can be a TMI
                    ta.add_trust_mark_specs(trust_mark_id=tmoConf[tmo]["trust_mark_id"],
                                            lifetime=86400,  
                                            ref=tmoConf[tmo]["ref"], 
                                            delegation_jwt=tmoConf[tmo]["trust_mark_issuers"][ta.get_entity_id()], 
                                            checker_type="none")

            # Add eduGAIN and REFEDs as trustmark issuers
            ta.add_trust_mark(trust_mark_id="https://edugain.org/member", trust_mark_issuer='https://edugain.oidfed.lab.surf.nl')
            ta.add_trust_mark(trust_mark_id="https://refeds.org/sirtfi", trust_mark_issuer=raConf[ra]['ta_url'])

            # Add eduGAIN as eduGAIN Membership TMI
            os.popen('cp templates/ta_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 
        
        # Write config to file
        ta.to_yaml(TESTBED_PATH+'/' +ra+ '/data/config.yaml')  # writes the config to file

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
