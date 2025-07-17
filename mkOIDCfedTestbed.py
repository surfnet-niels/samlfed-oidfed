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

from utils import p, pj, loadJSON, write_file, write_log, is_file_older_than_x_days, fetchFile

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

def parseFeds(fedsJson,fedsInUse, baseURL):
    RAs = {}

    for fedID in fedsJson.keys(): 
        if fedID in fedsInUse or len(fedsInUse) == 0:
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
                            'ta_url': 'https://'+''.join(fedsJson[fedID].get('country_code')[i])+'.'+fedID.lower()+ '.' + baseURL,
                            'subordinates': []
                        }

                        RAs[fedID_country] = thisFedData
            else:
                p(fedID + " skipped as not in use due to config")
    return RAs 

def main(argv):
    LOGDEBUG = True
    WRITETOLOG = False

    # ToDo: move all of this to a conf file
    ROOTPATH=os.getcwd()
    TESTBED_PATH = ROOTPATH + '/testbed'
    CONFIG_PATH = ROOTPATH + '/config/'
    INPUT_PATH = ROOTPATH + '/feeds/'
    OUTPUT_PATH = ROOTPATH + '/var/www/oidcfed/'
    KEYS_PATH = TESTBED_PATH + '/keys/'
    TESTBED_BASEURL= 'oidf.lab.surf.nl'
    DOCKER_CONTAINER_NAME = "testbed-~~container_name~~-1"

    # a local file contains all the secrets we need to keep secure. The template for this file is found in config/local.json.template
    localConf = CONFIG_PATH + 'local_config.json'
    config = loadJSON(localConf)
    pj(config)
    EMAIL = config["email"]

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

    # Read Feds into Config, Optionally provide an array of Fed names to include
    #raConf = parseFeds(allFeds, ['IDEM', 'SURFCONEXT', 'HAKA'], TESTBED_BASEURL)
    raConf = parseFeds(allFeds, [], TESTBED_BASEURL)

    # Add eduGAIN as a TA
    # ToDo: move to config
    raConf["edugain"] = {
        "display_name": 'eduGAIN',
        "name":  'edugain',
        "reg_auth": '',
        "country_code": '',
        "md_url": '',
        "ta_url": 'https://edugain.oidf.lab.surf.nl',
        "subordinates": []
    }

    #
    # Configure TEST RPs
    # Note all other RPs will register lateron
    #
    rpConf=loadJSON("config/rp/config.json")
        
    # Config for TMIs that are not part of TAs
    tmiConf=loadJSON("config/tmi/config.json")

    # Config for TM 
    tmConf=loadJSON("config/tm/config.json")

    # Config for TMOs
    tmoConf=loadJSON("config/tmo/config.json")

    # Specials

    # eduGAIN has all national feds as its subordinates
    for ta in raConf.keys():
        raConf["edugain"]["subordinates"].append(expandTestbedURL(ta,TESTBED_BASEURL))

    # The global RP is a member of all federations, hence has all as TA and authority hint
    for ta in raConf.keys():
        rpConf["global-rp"]["tas"].append(ta)

    #
    # Make sure we have all config dirs
    # TODO: make function for this?
    # Caddy proxy 
    os.makedirs(TESTBED_PATH+'/caddy', mode=0o777, exist_ok=True)
    # A static server for a testbed overview page
    os.makedirs(TESTBED_PATH+'/testbed/conf', mode=0o777, exist_ok=True)
    os.makedirs(TESTBED_PATH+'/testbed/data/html', mode=0o777, exist_ok=True)
    # A static server for LEAFS
    os.makedirs(TESTBED_PATH+'/leafs/conf', mode=0o777, exist_ok=True)
    os.makedirs(TESTBED_PATH+'/leafs/data/html', mode=0o777, exist_ok=True)

    # Copy incubator favicon static containers
    os.popen('cp templates/favicon.ico '+TESTBED_PATH+ '/leafs/data/html/favicon.ico')
    os.popen('cp templates/favicon.ico '+TESTBED_PATH+ '/testbed/data/html/favicon.ico')   

    # Create nginx config for static containers
    os.popen('cp templates/nginx_default.conf '+TESTBED_PATH+ '/leafs/conf/default.conf')
    os.popen('cp templates/nginx_default.conf '+TESTBED_PATH+ '/testbed/conf/default.conf')

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
                TESTBED_PATH+'/' +rp+ '/data/config.yaml:/config.yaml:ro'
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

    tb['services']['testbed'] = {
            "image": "'nginx:1-alpine'",
            "networks": {"caddy": ''},
            "volumes": [
                TESTBED_PATH + "/testbed/conf/default.conf:/etc/nginx/conf.d/default.conf",
                TESTBED_PATH + "/testbed/data/html/:/var/www/html",
            ],
            "expose": ["8765"],
            "stop_grace_period": "'500ms'"
    }

    tb['services']['leafs'] = {
            "image": "'nginx:1-alpine'",
            "networks": {"caddy": ''},
            "volumes": [
                TESTBED_PATH + "/leafs/conf/default.conf:/etc/nginx/conf.d/default.conf",
                TESTBED_PATH + "/leafs/data/html/:/var/www/html",
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

    ##################################################################################################################################
    #
    # Build configuration for various containers
    #
    ##################################################################################################################################

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

            ta.add_trust_mark_owner(trust_mark_id="https://refeds.org/sirtfi", entity_id=expandTestbedURL("refeds",TESTBED_BASEURL),jwks=tmoConf['refeds']['jwks'])
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
            ta.add_trust_mark(trust_mark_id="https://edugain.org/member", trust_mark_issuer=expandTestbedURL("edugain",TESTBED_BASEURL))

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
                                            entity_id=expandTestbedURL(tmo,TESTBED_BASEURL),
                                            jwks=tmoConf[tmo]['jwks'])

                    # Add TrustMark Spec so this TA can be a TMI
                    ta.add_trust_mark_spec(trust_mark_id=tmoConf[tmo]["trust_mark_id"],
                                            lifetime=86400,  
                                            ref=tmoConf[tmo]["ref"], 
                                            delegation_jwt=tmoConf[tmo]["trust_mark_issuers"][ta.get_entity_id()], 
                                            checker_type="none")

            # Add eduGAIN and REFEDs as trustmark issuers
            # ToDo: read this from config
            ta.add_trust_mark(trust_mark_id="https://edugain.org/member", trust_mark_issuer=expandTestbedURL("edugain",TESTBED_BASEURL))
            ta.add_trust_mark(trust_mark_id="https://refeds.org/sirtfi", trust_mark_issuer=raConf[ra]['ta_url'])

            # Add eduGAIN as eduGAIN Membership TMI
            os.popen('cp templates/ta_metadata-policy.json '+TESTBED_PATH+'/' +ra+ '/data/metadata-policy.json') 

        # Write config to file
        ta.to_yaml(TESTBED_PATH+'/' +ra+ '/data/config.yaml')  # writes the config to file


    #
    # Write config from template for all Test RPs
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
    
    if config["use_letsencrypt"]:
        caddyConf.append('\n{\n     email '+ EMAIL +'\n}  ')
    else:
        caddyConf.append('''
{
    email '''+ EMAIL +'''
    acme_ca '''+ config["acme_ca"] +'''
    acme_eab {
        key_id '''+ config["acme_eab"]["key_id"] +'''
        mac_key '''+ config["acme_eab"]["mac_key"] +'''
    }
}
    ''')

    # Add testbed static nginx
    caddyConf.append('\ntestbed.'+ TESTBED_BASEURL + ' {\n     reverse_proxy testbed:8765\n}  ')
    # Add leafs static nginx
    caddyConf.append('\nleafs.'+ TESTBED_BASEURL + ' {\n     reverse_proxy leafs:8765\n}  ')

    for ra in raConf.keys():
        caddyConf.append('\n' + ra +'.'+ TESTBED_BASEURL + ' {\n     reverse_proxy '+ra+':8765\n}  ')
    for rp in rpConf.keys():
        caddyConf.append('\n' + rp +'.'+ TESTBED_BASEURL + ' {\n     reverse_proxy '+rp+':8765\n}  ')   
    for tmi in tmiConf.keys():
        if tmiConf[tmi]["tmi_type"] == "standalone":
            caddyConf.append('\n' + tmi +'.'+ TESTBED_BASEURL + ' {\n     reverse_proxy '+tmi+':8765\n}  ')  
    write_file('\n'.join(caddyConf), TESTBED_PATH+'/caddy/Caddyfile', mkpath=False, overwrite=True)

    # Relations

    # Now write out all relations between the entities so these can be fed to the software

    # Register subordinates
    subordinates = {}
    for ta in raConf.keys():
        if "subordinates" in raConf[ta]:
            subordinates[ta] = []

            # All TAs have the global RP as a subordinate
            raConf[ta]["subordinates"].append(expandTestbedURL("global-rp",TESTBED_BASEURL))

            for sub in raConf[ta]["subordinates"]:
                subordinates[ta].append(sub)

            # All TMIs that have this ta as a TA must be a subordinate of this TA
            for tmi in tmiConf.keys():
                if tmiConf[tmi]["tmi_type"] == "standalone" and ta in tmiConf[tmi]["tas"]:
                    subordinates[ta].append(expandTestbedURL(tmi,TESTBED_BASEURL))

            # Add additional Test RPs
            for rp in rpConf.keys():
                if ta in rpConf[rp]["tas"] and ta != "edugain":
                    subordinates[ta].append(expandTestbedURL(rp,TESTBED_BASEURL))

    write_file(subordinates, CONFIG_PATH+'subordinates/ia.subordinate.json', mkpath=False, overwrite=True, type="json")

    # Create executable to inject subordinates into reevant containers
    # subs = ["#! /bin/bash"]
    # for ta in subordinates.keys():
    #     for entity in subordinates[ta]:
    #         subs.append("echo \""+entity+" \"\n && docker exec " +DOCKER_CONTAINER_NAME.replace("~~container_name~~", ta)+ " /tacli -c /data/config.yaml subordinates add " + entity)

    # write_file('\n'.join(subs), TESTBED_PATH+'/non_leaf_subordinates.sh', mkpath=False, overwrite=True)

    # Create a simple testbed overview page
    testbedPage = "<html><title>eduGAIN OIDfed testbed page</title><body>"
    
    raTable = '''
    <table>
        <tr>
            <td colspan="3">Trust Anchors</td>
        </tr>
        <tr>
            <td>Name</td>
            <td>Country</td>
            <td>Trust Anchor</td>
            <td width="5"></td>
            <td>Entities</td>
        </tr>
    '''

    for ra in raConf.keys():
        raTable += '''
            <tr>
                <td>'''+raConf[ra]["display_name"]+'''</td>
                <td>'''+raConf[ra]["country_code"]+'''</td>
                <td><a href="'''+raConf[ra]["ta_url"]+'''/.well-known/openid-federation">'''+raConf[ra]["ta_url"]+'''</a></td>
                <td width="5"></td>
                <td><a href="'''+raConf[ra]["ta_url"]+'''/list">Entities</a></td>
            </tr>
        '''
    raTable += '</table>'
    testbedPage += raTable + "</body></html>"

    write_file(testbedPage, TESTBED_PATH + '/testbed/data/html/' +'index.html', mkpath=False, overwrite=True)
    #os.popen('cp templates/nginx_default.conf '+TESTBED_PATH+ '/testbed/conf/default.conf') 

if __name__ == "__main__":
    main(sys.argv[1:])
