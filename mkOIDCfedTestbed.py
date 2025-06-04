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
from oidfconfig import ta_config
from oidfconfig import tmi_config
from oidfconfig import tmo_config
from oidfconfig import trustmark
from oidfconfig import trust_mark_spec
from oidfconfig import rp_config

##################################################################################################################################
#
# Config and logs handling functions
#
##################################################################################################################################
def loadJSON(json_file):
   with open(json_file) as json_file:
     return json.load(json_file)

def p(message, writetolog=False):
   if writetolog:
      write_log(message)
   else:
      print(message)
    
def pj(the_json, writetolog=False):
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

def expandTestbedURLs(feds, testbed_url):
    fedUrls = []
    
    for fed in feds:
        fedUrls.append(expandTestbedURL(fed, testbed_url))                  
    return fedUrls

def expandTestbedURL(fed, testbed_url):
    return "https://" + fed + "." + testbed_url

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
    LOGDEBUG = True
    WRITETOLOG = False

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
    # Deployment Configuration
    # Load RAs from eduGAIN
    #   
    if FETCHEDUGAINURL:
        edugainFedsURL = 'https://technical.edugain.org/api.php?action=list_feds_full'
        allFeds = getFeds(edugainFedsURL, INPUT_PATH)
    else:
        allFeds = loadJSON(INPUT_PATH + 'allfeds.json')

    # Read Feds into Config, provide an array of Fed names to filter
    raConf = parseFeds(allFeds, ['IDEM', 'SURFCONEXT', 'HAKA'])

    # Add eduGAIN as a TA
    raConf["edugain"] = {
        "display_name": 'eduGAIN',
        "name":  'edugain',
        "reg_auth": '',
        "country_code": '',
        "md_url": '',
        "ta_url": 'https://edugain.oidfed.lab.surf.nl'
    }

    #
    # Configure Test RPs
    # Note all other RPs will register lateron
    #
    rpConfFile = '''{
        "surf-rp": {
            "name": "SURF test RP",
            "url": "surf-rp",
            "tas": ["nl.surfconext", "edugain"],
            "tms": [
                {"https://edugain.org/member": "edugain"},
                {"https://erasmus-plus.ec.europa.eu": "erasmus-plus"}
            ]
        }, 
        "puhuri-rp": {
            "name": "Puhuri test RP",
            "url": "puhuri-rp",
            "tas": ["fi.haka", "edugain"],
            "tms": [
                {"https://edugain.org/member": "edugain"}
            ]
        }, 
        "helsinki-rp": {
            "name": "Helsinki test RP",
            "url": "helsinki-rp",
            "tas": ["fi.haka", "edugain"],
            "tms": [
                {"https://edugain.org/member": "edugain"}
            ]
        }, 
        "garr-rp": {
            "name": "GARR test RP",
            "url": "garr-rp",
            "tas": ["it.garr", "edugain"],
            "tms": [
                {"https://edugain.org/member": "edugain"}
            ]
        }
    }'''
    rpConf=json.loads(rpConfFile)

    # Config for TMIs that are not part of TAs
    tmiConfFile = '''{
        "edugain": {
            "name": "eduGAIN Membership Trustmark Issuer",
            "url": "edugain",
            "tas": [],
            "trust_mark_ids": ["https://edugain.org/member"],
            "tmi_type": "ta"
        },
        "erasmus-plus": {
            "name": "Erasmus+ Trustmark Issuer",
            "url": "erasmus-plus",
            "tas": ["edugain"],
            "trust_mark_ids": ["https://erasmus-plus.ec.europa.eu"],
            "tmi_type": "standalone"
        }
    }'''
    tmiConf=json.loads(tmiConfFile)

    tmConfFile = '''{
        "https://edugain.org/member": {
            "name": "eduGAIN Membership",
            "issuer": "edugain",
            "logo_uri": "https://edugain.org/wp-content/uploads/2018/02/eduGAIN.jpg",
            "ref": "",
            "lifetime": 86400
        },
        "https://erasmus-plus.ec.europa.eu": {
            "name": "Erasmus+ Trustmark",
            "issuer": "erasmus-plus",
            "logo_uri": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Erasmus%2B_Logo.svg/799px-Erasmus%2B_Logo.svg.png",
            "ref": "https://erasmus-plues.ec.europa.eu/ref",
            "lifetime": 86400
        }        
    }'''
    tmConf=json.loads(tmConfFile)

    # Config for TMOs
    tmoConfFile = '''{
        "refeds": {
            "name": "REFEDs Trustmark Owner",
            "tas": ["edugain"],
            "jwks": null,
            "trust_mark_id": "https://refeds.org/sirtfi",
            "ref": "https://refeds.org/wp-content/uploads/2022/08/Sirtfi-v2.pdf",
            "trust_mark_issuers": [
                "nl.surfconext",
                "it.idem",
                "us.incommon",
                "fi.haka",
                "se.swamid"
            ]
        } 
    }'''
    tmoConf=json.loads(tmoConfFile)

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

    ##################################################################################################################################
    #
    # Build docker-compose container definition
    #
    ##################################################################################################################################
    tb = {
        "services": {}, 
        "networks": {"caddy": ''}
    }

    # Add TAs
    for ra in raConf.keys():
        tb['services'][ra] = {
            "image": "'myoidc/oidfed-gota'",
            "networks": {"caddy": ''},
            "volumes": [TESTBED_PATH+'/' +ra+ '/data:/data'],
            "expose": ["8765"],
            "stop_grace_period": "'500ms'"
        }

    # Add (Standalone) TMIs
    for tmi in tmiConf.keys():
        if tmiConf[tmi]["tmi_type"] == "standalone":
            tb['services'][tmi] = {
                "image": "'myoidc/oidfed-gota'",
                "networks": {"caddy": ''},
                "volumes": [TESTBED_PATH+'/' +tmi+ '/data:/data'],
                "expose": ["8765"],
                "stop_grace_period": "'500ms'"
            }

    # Add (test) RPs
    for rp in rpConf.keys():
        tb['services'][rp] = {
            "image": "'myoidc/oidfed-gorp'",
            "networks": {"caddy": ''},
            "volumes": [
                TESTBED_PATH+'/' +rp+ '/data:/data',
                TESTBED_PATH+'/' +rp+ '/config.yaml:/config.yaml:ro'
            ],
            "expose": ["8765"],
            "stop_grace_period": "'500ms'"
        }

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
        tmo.set_trust_mark_owner(trust_mark_owner="https://" +this_tmo +"." + TESTBED_BASEURL)
        tmo.add_trust_mark(trust_mark_id=tmoConf[this_tmo]["trust_mark_id"], 
                           trust_mark_issuers=expandTestbedURLs(tmoConf[this_tmo]["trust_mark_issuers"],TESTBED_BASEURL)
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

        tmoConf[this_tmo]['jwks'] = tmoDel['jwks']
        tmoConf[this_tmo]['trust_mark_issuers'] = {}
        # loop over TMs for this TMO
        for tm in tmoDel['trust_marks']:
            for tmi in tm["trust_mark_issuers"]:
                tmoConf[this_tmo]['trust_mark_issuers'][tmi['entity_id']] = tmi['delegation_jwt']

    # Add Trust Mark Issuers
    # These are stand alone TMIs. Some TAs may also be TMIs, that is part of TA config
    # Some TMIs may be issuing delegated TMIs for a given TMO
    for this_tmi in tmiConf.keys():
        tmi = tmi_config.from_yaml('templates/tmi_config.yaml')

        tmi.add_authority_hint(expandTestbedURL("edugain",TESTBED_BASEURL))
        tmi.set_entity_id(expandTestbedURL(tmiConf[this_tmi]["url"],TESTBED_BASEURL))
        tmi.set_organization_name(tmiConf[this_tmi]["name"])


        # Do we have any config for this TMI?
        if this_tmi in tmiConf:
            # Is it a 'standalone' TMI? 
            # (Others might be part of a TA, which we can ignore here, these are configured as part of the TA)
            if tmiConf[this_tmi]["tmi_type"] == "standalone":
                for tm in tmConf.keys():
                    if tm in tmiConf[this_tmi]["trust_mark_ids"]:
                        tmi.add_trust_mark_spec(trust_mark_id=tm, 
                                            ref=tmConf[tm]["ref"], 
                                            logo_uri= tmConf[tm]["logo_uri"],
                                            lifetime=tmConf[tm]["lifetime"], 
                                            checker_type="none")

                        tmi.add_trust_mark(tm, expandTestbedURL(tmConf[tm]["issuer"],TESTBED_BASEURL))

    tmi.to_yaml(TESTBED_PATH+'/' +this_tmi+ '/data/config.yaml')  # writes the config to file

    #
    # Write config from template for all TAs
    #
    for ra in raConf.keys():
        # read the TA config template
        ta = ta_config.from_yaml('templates/ta_config.yaml')

        # set entity_id & organization_name
        ta.set_entity_id(raConf[ra]["ta_url"])
        ta.set_organization_name(raConf[ra]["display_name"])

        # Update values as needed
        if ra == 'edugain':
            # Set eduGAIN as the root
            ta.add_authority_hint(None)

            # TODO: for edugain replace with proper YAML handling
            # Add REFEDs as SIRTFI trustmark owner

            ta.add_trust_mark_owner(trust_mark_id="https://refeds.org/sirtfi", entity_id="https://refeds.oidfed.lab.surf.nl",jwks=tmoConf['refeds']['jwks'])
            ta.add_trust_mark_spec(trust_mark_id="https://edugain.org/member", 
                                    ref="https://www.edugain.org", 
                                    logo_uri= "https://edugain.org/wp-content/uploads/2018/02/eduGAIN.jpg",
                                    lifetime=86400, 
                                    checker_type="trust_path",
                                    trust_anchors=expandTestbedURLs(["nl.surfconext",
                                                    "it.idem",
                                                    "us.incommon",
                                                    "fi.haka",
                                                    "se.swamid"],TESTBED_BASEURL)
                                    )

            # Add trustmarks issuers
            # ToDo: read this from config
            ta.add_trust_mark_issuer('https://edugain.org/member', expandTestbedURL("edugain",TESTBED_BASEURL))
            ta.add_trust_mark_issuer('https://erasmus-plus.ec.europa.eu', expandTestbedURL("erasmus-plus",TESTBED_BASEURL))
            ta.add_trust_mark_issuer('http://www.csc.fi/haka/member', expandTestbedURL("fi.haka",TESTBED_BASEURL))
            ta.add_trust_mark_issuer('https://puhuri.io',  expandTestbedURL("puhuri.io",TESTBED_BASEURL))                        
            ta.add_trust_mark_issuer('https://incommon.org/federation/member', expandTestbedURL("us.incommon",TESTBED_BASEURL))            

            # Add eduGAIN as trustmark
            # ToDo: read this from config
            ta.add_trust_mark(trust_mark_id="https://edugain.org/member", trust_mark_issuer='https://edugain.oidfed.lab.surf.nl')

            # Copy over edugain policy template 
            os.popen('cp templates/edugain_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 

        else:
            # for now all Tas have eduGAIN as the parent
            ta.add_authority_hint(raConf["edugain"]['ta_url'])

            # Add TMOs to the TAs
            for tmo in tmoConf:
                # If we find a TA in the TMO config we need to add it, to make this TA an TMI on behalf of the TMO
                if ta.get_entity_id() in tmoConf[tmo]["trust_mark_issuers"]:
                    p("Found TMI " + tmo + " I must issue for")

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
            # ToDo: read this from config
            ta.add_trust_mark(trust_mark_id="https://edugain.org/member", trust_mark_issuer='https://edugain.oidfed.lab.surf.nl')
            ta.add_trust_mark(trust_mark_id="https://refeds.org/sirtfi", trust_mark_issuer=raConf[ra]['ta_url'])

            # Add eduGAIN as eduGAIN Membership TMI
            os.popen('cp templates/ta_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 
        
        # Write config to file
        ta.to_yaml(TESTBED_PATH+'/' +ra+ '/data/config.yaml')  # writes the config to file


    #
    # Write config from template for all TAs
    #
    for this_rp in rpConf.keys():
        # read the RP config template
        rp = rp_config.from_yaml('templates/rp_config.yaml')

        # set entity_id & organization_name
        rp.set_entity_id(expandTestbedURL(rpConf[this_rp]["url"],TESTBED_BASEURL))
        rp.set_organization_name(rpConf[this_rp]["name"])
        for a in rpConf[this_rp]["tas"]:
            rp.add_authority_hint(expandTestbedURL(a,TESTBED_BASEURL))
            rp.add_trust_anchor(expandTestbedURL(a,TESTBED_BASEURL))

        for tm in rpConf[this_rp]["tms"]:
            for trust_mark_id, trust_mark_issuer in tm.items():
                rp.add_trust_mark(trust_mark_id, expandTestbedURL(trust_mark_issuer,TESTBED_BASEURL))

        # Write config to file
        rp.to_yaml(TESTBED_PATH+'/' +this_rp+ '/data/config.yaml')  # writes the config to file
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
    for rp in rpConf.keys():
        caddyConf.append('\n' + rp +'.'+ TESTBED_BASEURL + ' {\n     reverse_proxy '+rp+':8765\n}  ')   
    for tmi in tmiConf.keys():
        if tmiConf[tmi]["tmi_type"] == "standalone":
            caddyConf.append('\n' + tmi +'.'+ TESTBED_BASEURL + ' {\n     reverse_proxy '+tmi+':8765\n}  ')  
    write_file('\n'.join(caddyConf), TESTBED_PATH+'/caddy/Caddyfile', mkpath=False, overwrite=True)

if __name__ == "__main__":
    main(sys.argv[1:])
