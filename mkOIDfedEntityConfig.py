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
   if writetolog:
      write_log(json.dumps(the_json, indent=4, sort_keys=False), writetolog)       
   else:    
      p(json.dumps(the_json, indent=4, sort_keys=False), writetolog)

def write_log(message):
   datestamp = (datetime.datetime.now()).strftime("%Y-%m-%d")
   timestamp = (datetime.datetime.now()).strftime("%Y-%m-%d %X")
   f = open("./logs/" + datestamp + "_status.log", "a")
   f.write(timestamp +" "+ message+"\n")
   f.close()

def write_file(contents, filepath, mkpath=True, overwrite=False):
   if mkpath:
      Path(filepath).mkdir(parents=True, exist_ok=overwrite)

   f = open(filepath, "a")
   f.write(contents+"\n")
   f.close()

##################################################################################################################################
#
# Metadata url/file handling functions
#
##################################################################################################################################

def is_file_older_than_x_days(file, days=1): 
    file_time = os.path.getmtime(file) 
    # Check against 24 hours 
    if (time.time() - file_time) / 3600 > 24*days: 
        return True
    else: 
        return False

def fetchFile(url, file_path):
  try:
    urllib.request.urlretrieve(url, file_path)
    return True
  except Exception as error:
    p("ERROR: Could not download from URL: " + url, LOGDEBUG)
    p("ERROR: Encountered " + type(error).__name__, LOGDEBUG)
    return False

def parseMetadataXML(file_path):
    try:
      with open(file_path) as fd:
          ent = xmltodict.parse(fd.read()) # type: ignore
          return ent

    except:
      print("ERROR: Could not parse " +file_path)
      return {}    

def fetchMetadata(md_urls, raname, input_path):

   metadataSet = []

   for i in range(len(md_urls)):
      md_url = md_urls[i]

      file_path = input_path + raname.replace(" ", "_") + '_' + str(i) + '.xml'

      if os.path.isfile(file_path) and not (is_file_older_than_x_days(file_path, 1)):
         p("INFO: " + raname + " metadata still up to date, skipping download", LOGDEBUG)
      else:
         p("INFO: " + raname + " metadata out of date, downloading from " + md_url, LOGDEBUG)

         if (fetchFile(md_url, file_path)):
            p("INFO: Downloaded metadata: " + md_url + " to file location: " + file_path, LOGDEBUG)
         else:
            p("ERROR: Could not download metadata for " + raname, LOGDEBUG)
            file_path = None
            
      metadataSet.append(file_path)
       
      if len(md_urls) == 0:
         p("ERROR: No metadata URL provided for RA " + raname, LOGDEBUG)

   return metadataSet
 
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
                  'ta_url': 'https://'+''.join(fedsJson[fedID].get('country_code')[i])+'.'+fedID.lower()+ '.oidf.lab.surf.nl'}

               RAs[fedID_country] = thisFedData
   return RAs  

def setRAdata(raconf, input_path, edugain_ra_uri):
  # Read RA config and loads RA metadata 
  RAs={}

  for ra in raconf.keys():
     RAs[ra] = {} 
      
     RAs[ra]["md_url"] = raconf[ra]["md_url"]
     RAs[ra]["ra_display_name"] = raconf[ra]["display_name"]
     RAs[ra]["ra_name"] = ra
     RAs[ra]["reg_auth"] = raconf[ra]["reg_auth"]
     RAs[ra]["ra_hash"] = hashSHA1(ra)
     RAs[ra]["country_code"] = raconf[ra]["country_code"]
     RAs[ra]["filepath"] = []
     RAs[ra]["ta_url"] = raconf[ra]["ta_url"]

  return RAs

##################################################################################################################################
#
# SAML Metadata processing functions
#
##################################################################################################################################

def getDescriptor(type):
   if (type.lower() == 'idp'):
      return "./md:IDPSSODescriptor"
   if (type.lower() == 'sp'):
      return "./md:SPSSODescriptor"

# Get entityID
def getEntityID(EntityDescriptor, namespaces):
    return EntityDescriptor.get('entityID')

# Get hased EntityID
def hashSHA1(aString):    
    return hashlib.sha1(aString.encode('utf-8')).hexdigest()

#Get XML element
def getElement(EntityDescriptor,namespaces, elementName, entityType,lang='en'):
   match elementName:
      case 'description':
         xPathString = getDescriptor(entityType) + "/md:Extensions/mdui:UIInfo/mdui:Description"
      case 'servicename':
         xPathString = getDescriptor(entityType) + "/md:AttributeConsumingService/md:ServiceName"
      case 'displayname':
         xPathString = getDescriptor(entityType) + "/md:Extensions/mdui:UIInfo/mdui:DisplayName"
      case 'informationurl':
         xPathString = getDescriptor(entityType) + "/md:Extensions/mdui:UIInfo/mdui:InformationURL"
      case 'privacystatementurl':
         xPathString = getDescriptor(entityType) + "/md:Extensions/mdui:UIInfo/mdui:PrivacyStatementURL"
      case 'organizationname':
         xPathString = "./md:Organization/md:OrganizationName"
      case 'organizationurl':
         xPathString = "./md:Organization/md:OrganizationURL"       
      case "logo":
         xPathString = getDescriptor(entityType) + "/md:Extensions/mdui:UIInfo/mdui:Logo" 
      case 'shibscope':
         xPathString = getDescriptor(entityType) + "/md:Extensions/shibmd:Scope"
      case _:
         raise Exception("Unsupported element type " +elementName+ " requested") 

   elements = EntityDescriptor.findall(xPathString, namespaces)

   elem_dict = dict()
   for elem in elements:
       lang = elem.get("{http://www.w3.org/XML/1998/namespace}lang")
       elem_dict[lang] = elem.text

   return elem_dict

# Get MDUI Logo BIG
def getLogoBig(EntityDescriptor,namespaces,entType='idp'):

    entityType = ""
    if (entType.lower() == 'idp'):
       entityType = "./md:IDPSSODescriptor"
    if (entType.lower() == 'sp'):
       entityType = "./md:SPSSODescriptor"
    
    logoUrl = ""
    logos = EntityDescriptor.findall("%s/md:Extensions/mdui:UIInfo/mdui:Logo[@xml:lang='it']" % entityType,namespaces)
    if (len(logos) != 0):
       for logo in logos:
           logoHeight = logo.get("height")
           logoWidth = logo.get("width")
           if (logoHeight != logoWidth):
              # Avoid "embedded" logos
              if ("data:image" in logo.text):
                 logoUrl = "embeddedLogo"
                 return logoUrl
              else:
                 logoUrl = logo.text
                 return logoUrl
    else:
       logos = EntityDescriptor.findall("%s/md:Extensions/mdui:UIInfo/mdui:Logo[@xml:lang='en']" % entityType,namespaces)
       if (len(logos) != 0):
          for logo in logos:
              logoHeight = logo.get("height")
              logoWidth = logo.get("width")
              if (logoHeight != logoWidth):
                 # Avoid "embedded" logos
                 if ("data:image" in logo.text):
                    logoUrl = "embeddedLogo"
                    return logoUrl
                 else:
                    logoUrl = logo.text
                    return logoUrl
       else:
           logos = EntityDescriptor.findall("%s/md:Extensions/mdui:UIInfo/mdui:Logo" % entityType,namespaces)
           if (len(logos) != 0):
              for logo in logos:
                  logoHeight = logo.get("height")
                  logoWidth = logo.get("width")
                  if (logoHeight != logoWidth):
                     # Avoid "embedded" logos
                     if ("data:image" in logo.text):
                        logoUrl = "embeddedLogo"
                        return logoUrl
                     else:
                        logoUrl = logo.text
                        return logoUrl
           else:
              return ""

# Get MDUI Logo SMALL
def getLogoSmall(EntityDescriptor,namespaces,entType='idp',format="html"):

   logos = EntityDescriptor.findall("%s/md:Extensions/mdui:UIInfo/mdui:Logo" % getDescriptor(entType), namespaces)

   logo_dict = dict()

   for logo in logos:
       lang = logo.get("{http://www.w3.org/XML/1998/namespace}lang")
       logo_dict[lang] = logo.text

   return logo_dict

# Get OrganizationURL
# def getOrganizationURL(EntityDescriptor,namespaces,lang='en'):
#     orgUrl = EntityDescriptor.find("./md:Organization/md:OrganizationURL[@xml:lang='%s']" % lang,namespaces)

#     if (orgUrl != None):
#        return orgUrl.text
#     else:
#        return ""

# Get RequestedAttribute
def getRequestedAttribute(EntityDescriptor,namespaces):
    reqAttr = EntityDescriptor.findall("./md:SPSSODescriptor/md:AttributeConsumingService/md:RequestedAttribute", namespaces)

    requireList = list()
    requestedList = list()
    requestedAttributes = dict()

    if (len(reqAttr) != 0):
       for ra in reqAttr:
           if (ra.get('isRequired') == "true"):
              requireList.append(ra.get('FriendlyName'))
           else:
              requestedList.append(ra.get('FriendlyName'))

    requestedAttributes['required'] = requireList
    requestedAttributes['requested'] = requestedList

    return requestedAttributes


# Get Contacts
def getContacts(EntityDescriptor,namespaces,contactType='technical', format="html"):
   #ToDo: add a more strict scan for securtiy as 'other may also be used in another way'

   name=''
   mail=''
   contactsList = list()
   contactsDict = {}
   
   contacts = EntityDescriptor.findall("./md:ContactPerson[@contactType='"+contactType.lower()+"']/md:EmailAddress", namespaces)
   contactsGivenName = EntityDescriptor.findall("./md:ContactPerson[@contactType='"+contactType.lower()+"']/md:GivenName", namespaces)
   contactsSurName = EntityDescriptor.findall("./md:ContactPerson[@contactType='"+contactType.lower()+"']/md:SurName", namespaces)

   cname = "" 
   if (len(contactsGivenName) != 0):
      for cgn in contactsGivenName:
         cname = cgn.text

   if (len(contactsSurName) != 0):
      for csn in contactsSurName:
         cname = cname + " " + csn.text

   if (len(cname) != 0):
      name = cname.strip()              

   if (len(contacts) != 0):
      for ctc in contacts:
         if ctc.text.startswith("mailto:"):
            mail = ctc.text.replace("mailto:", "")
         else:
            mail = contactsList.append(ctc.text)

   if format=="html":
      contactsList.append(name) 
      contactsList.append(mail)
      return '<br/>'.join(contactsList)
   else:
      contactsDict['name']=name
      contactsDict['email']=mail
      return contactsDict

def getEntityCategories(EntityDescriptor):
   entCat = []
   
   for ent in EntityDescriptor:
      entCat.append(ent.text)

   return entCat
   
def formatPrivacy(privacyDict, format="html", lang="en"):
   #ToDO: propper language processing in case of HTML
   privacy = {}

   if len(privacyDict)!=0:
      match format:
         case "html":
            privacy = "<ul>"
            for lang in privacyDict:
               flag = lang
               if lang == "en":
                  flag = "gb"
            privacy = privacy + "<li><a href='"+privacyDict[lang]+ "' target='_blank'><img src='https://flagcdn.com/24x18/"+flag+".png' alt='Info "+lang.upper()+"' height='18' width='24' /></a></li>"
            privacy = privacy + "</ul>"      
         case "json":
            privacy = privacyDict
   
   return privacy

def formatContacts(contacts, format="html", lang="en"):
   #ToDO: propper language processing in case of HTML
   if len(contacts)!=0:
      match format:
         case "json":
            formatted_contact = []
            for type, value in contacts.items():
               formatted_contact.append(type + ": " + value)
               
            return {'': formatted_contact}
         case _:
            return ""

##################################################################################################################################
#
# OIDCfed stuff
#
##################################################################################################################################

def mkJWK(entityHash): 

   kid= hashSHA1(entityHash + str(datetime.datetime.now()))
   
   return jwk.JWK.generate(kty='EC', crv='P-256', use='sig', kid=kid)

def exportKey(keys, type="public"):
   if type=="private":
      return keys.export(private_key=True)
   else:
      return keys.export(private_key=False)

def updateOIDCfedMetadata(leaf, element, elementValue, action="append"):
  
   match element:
      case 'authority_hints':
         if action == "append":
            leaf["metadata"]['authority_hints'].append(elementValue)

def mkOIDCfedMetadata(leaf_dict, baseURL, def_lang="en"):

   if leaf_dict['type'] == 'op':
      openid_provider=OrderedDict([
         ('token_endpoint_auth_methods_supported', ["client_secret_basic"]),
         ('claims_parameter_supported', True),
         ('request_parameter_supported', True),
         ('request_uri_parameter_supported', True),
         ('require_request_uri_registration', False),
         ('grant_types_supported', ["authorization_code", "implicit", "refresh_token", "urn:ietf:params:oauth:grant-type:device_code", "urn:ietf:params:oauth:grant-type:token-exchange"]),
         ('jwks_uri', baseURL + 'leafs/' + leaf_dict['id']+'/OIDC/jwks'),
         ('scopes_supported', ["openid", "profile", "email", "eduperson_assurance", "eduperson_entitlement", "eduperson_orcid", "eduperson_principal_name", "eduperson_scoped_affiliation", "voperson_external_affiliation", "voperson_external_id", "voperson_id", "aarc", "ssh_public_key", "orcid", "schac_home_organization", "schac_personal_unique_code"]),
         ('response_types_supported', ["code", "id_token token"]),
         ('response_modes_supported', ["query", "fragment", "form_post"]),
         ('subject_types_supported', ["public", "pairwise"]),
         ('id_token_signing_alg_values_supported', ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512", "HS256", "HS384", "HS512"]),
         ('userinfo_signing_alg_values_supported', ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512", "HS256", "HS384", "HS512"]),
         ('request_object_signing_alg_values_supported', ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512", "HS256", "HS384", "HS512"]),
         ('claim_types_supported', ["normal"]),
         ('claims_supported', ["sub", "eduperson_targeted_id", "eduperson_unique_id", "eduperson_orcid", "eaahash", "uid", "name", "given_name", "email", "name", "family_name", "eduperson_scoped_affiliation", "eduperson_affiliation", "eduperson_principal_name", "eduperson_entitlement", "eduperson_assurance", "schac_personal_unique_code", "schac_home_organization", "eidas_person_identifier", "ssh_public_key", "voperson_external_affiliation", "voperson_external_id", "voperson_id", "voperson_application_uid", "voperson_scoped_affiliation", "voperson_sor_id", "voperson_policy_agreement", "voperson_status", "eduid_cz_loa"]),
         ('code_challenge_methods_supported', ["S256"]),
         ('issuer', baseURL + 'leafs/' + leaf_dict['id']),
         ('authorization_endpoint', baseURL + 'leafs/' + leaf_dict['id']+'/saml2sp/OIDC/authorization'),
         ('token_endpoint', baseURL + 'leafs/' + leaf_dict['id']+'/OIDC/token'),
         ('userinfo_endpoint', baseURL + 'leafs/' + leaf_dict['id']+'/OIDC/userinfo'),
         ('introspection_endpoint', baseURL + 'leafs/' + leaf_dict['id']+'/OIDC/introspect'),
         ('revocation_endpoint', baseURL + 'leafs/' + leaf_dict['id']+'/OIDC/revoke')
      ]) 

      metadata=OrderedDict([
         ("openid_provider", openid_provider),
      ]) 

      if leaf_dict['resourceName'] is not None:
         appendConfig(metadata["openid_provider"], "display_name",leaf_dict['resourceName'], def_lang)

      if leaf_dict['logo'] is not None:
         appendConfig(metadata["openid_provider"], "logo_uri",leaf_dict['logo'], def_lang)
      
      if leaf_dict['description'] is not None:
         appendConfig(metadata["openid_provider"], "description",leaf_dict['description'], def_lang)

      if leaf_dict['info'] is not None:
         appendConfig(metadata["openid_provider"], "information_uri",leaf_dict['info'], def_lang)

      if 'privacy' in leaf_dict and leaf_dict['privacy'] is not None:
         appendConfig(metadata["openid_provider"], "policy_uri",leaf_dict['privacy'], def_lang)
      
      if 'orgName' in leaf_dict and leaf_dict['orgName'] is not None:
         appendConfig(metadata["openid_provider"], "organization_name",leaf_dict['orgName'], def_lang)

      if 'orgURL' in leaf_dict and leaf_dict['orgURL'] is not None:
         appendConfig(metadata["openid_provider"], "organization_uri",leaf_dict['orgURL'], def_lang)

      # if leaf_dict['contacts'] is not None:
      #    appendConfig(metadata["openid_provider"], "contacts", formatContacts(leaf_dict['contacts']), def_lang)
   
   if leaf_dict['type'] == 'rp':
      openid_relying_party=OrderedDict([
         ('client_name', leaf_dict['resourceName']),
         #('contacts',[leaf_dict['resourceContacts']['technical']['email']]),
         ('application_type', "web"),
         ('client_registration_types', ["automatic"]),
         ('grant_types',["refresh_token", "authorization_code"]),
         ('redirect_uris',[baseURL + "leafs/" + leaf_dict['id'] +"/oidc/rp/redirect"]),
         ('response_types', ["code"]),
         ('client_uri', leaf_dict['id']),
         ('subject_type', "pairwise"),
         ('tos_uri', baseURL + "leafs/" + leaf_dict['id'] +"/tos"),
         #('policy_uri', leaf_dict['privacy']["en"]),
         ('jwks',json.loads(exportKey(leaf_dict['keys'], "public")))
      ]) 

      metadata=OrderedDict([
         ("openid_relying_party", openid_relying_party),
      ]) 

      if leaf_dict['resourceName'] is not None:
         appendConfig(metadata["openid_relying_party"], "display_name",leaf_dict['resourceName'], def_lang)

      if leaf_dict['logo'] is not None:
         appendConfig(metadata["openid_relying_party"], "logo_uri",leaf_dict['logo'], def_lang)
      
      if leaf_dict['info'] is not None:
         appendConfig(metadata["openid_relying_party"], "information_uri",leaf_dict['info'], def_lang)
      
      if leaf_dict['description'] is not None:
         appendConfig(metadata["openid_relying_party"], "description",leaf_dict['description'], def_lang)

      if leaf_dict['privacy'] is not None:
         appendConfig(metadata["openid_relying_party"], "policy_uri",leaf_dict['privacy'], def_lang)

      if 'orgName' in leaf_dict and leaf_dict['orgName'] is not None:
         appendConfig(metadata["openid_relying_party"], "organization_name",leaf_dict['orgName'], def_lang)

      if 'orgURL' in leaf_dict and leaf_dict['orgURL'] is not None:
         appendConfig(metadata["openid_relying_party"], "organization_uri",leaf_dict['orgURL'], def_lang)    

      # if leaf_dict['contacts'] is not None:
      #    appendConfig(metadata["openid_relying_party"], "contacts", formatContacts(leaf_dict['contacts']), def_lang)
 

      # if leaf_dict['tos_uri'] is not None:
      #    pj(leaf_dict['tos_uri'])
      #    appendConfig(metadata["openid_relying_party"], "tos_uri",leaf_dict['tos_uri'], def_lang)


   now = datetime.datetime.now()
   iat = datetime.datetime.timestamp(now) # Today
   exp = datetime.datetime.timestamp(now + datetime.timedelta(days=3650)) # Set exp to 10 years

   # Build OIDCfed metadata
   leafMetadata = OrderedDict([
   ("iss", baseURL + "leafs/" + leaf_dict['id'] +"/"),
   ("sub", baseURL + "leafs/" + leaf_dict['id'] +"/"),
   ("iat", iat), 
   ("exp", exp), 
   ('jwks',json.loads(exportKey(leaf_dict['keys'], "public"))),
   ('metadata', metadata),
   #('trust_marks', leaf_dict['entityCategories']),
   ('authority_hints', [leaf_dict['taURL']]) # Lookup RA/TA dynamically
   ]) 

   return(leafMetadata)

def mkSignedOIDCfedMetadata(leafMetadata, key):
   encoded_data = jwt.JWT(header={"alg": "ES256", "type": "entity-statement+jwt", "kid": key.key_id},
                     claims=leafMetadata)
   encoded_data.make_signed_token(key)
   #encoded_data.serialize()  
   return encoded_data.serialize()

def appendConfig(configDict, configClaimName, elementDict, def_lang):
   for lang, elem in elementDict.items():
      # Set an element without lang using the default langage
      if lang == def_lang or lang is None:
         configDict[configClaimName] = elem

      if lang is not None:
         # Set langage specific content
         configDict[configClaimName+"#"+lang] = elem


################################################################################################################################
#
# testbed
#
##################################################################################################################################
def uploadMetadata(taUrl, sub, type="rp"):
   if type=='op':
     message =dict(entity_type="openid_provider", sub=sub)
   else:
     message =dict(entity_type="openid_relying_party", sub=sub)
  
   taUrl = taUrl + "/enroll"

   p(sub)
   p(taUrl)
   p("curl -i -X POST -H 'Content-Type: application/json' -d '"+str(message)+"' "+taUrl)

   #headers = {'Content-Type: application/json'}
   #res = urllib.request.post(taUrl, data=metadata, headers=headers)
   message = urllib.parse.urlencode(message).encode("utf-8")
   req = urllib.request.Request(taUrl, message)
   resp = urllib.request.urlopen(req).read().decode('utf-8')
   print(resp)
   sys.exit()

##################################################################################################################################
#
# Output files
#
##################################################################################################################################
def writeFile(contents, fileid, outputpath, filetype='json', mkParents=True, overwrite=True):
   
   match filetype:
      case 'json':
         leafsPath = outputpath + "leafs/" + fileid + "/"

         # Write the json to the leaf url
         Path(leafsPath).mkdir(parents=mkParents, exist_ok=overwrite)
         contentFile = open(leafsPath+"entity.json", "w",encoding=None)
         contentFile.write(json.dumps(contents,sort_keys=False, indent=4, ensure_ascii=False,separators=(',', ':')))
      case 'jwk':
         keysPath = outputpath + "keys/"
         
         # Write the jwk to the keys path outside of the public html url
         Path(keysPath).mkdir(parents=mkParents, exist_ok=overwrite)
         contentFile = open(keysPath+fileid+".jwk", "w",encoding=None)
         contentFile.write(json.dumps(contents,sort_keys=False, indent=4, ensure_ascii=False,separators=(',', ':')))
      case 'jwt':
         fedMetaPath = outputpath + "leafs/" + fileid + "/.well-known/"
         # Write the jwt diorectly to the metadata endpoint
         Path(fedMetaPath).mkdir(parents=mkParents, exist_ok=overwrite)
         contentFile = open(fedMetaPath+"openid-federation", "w",encoding=None)
         contentFile.write(str(contents))  
      case 'html':
         # info html path
         # Write a simple txt with the name and entityID of the institution for comparison
         leafsPath = outputpath + "leafs/" + fileid + "/"
         # Write the txt to the leaf url
         Path(leafsPath).mkdir(parents=mkParents, exist_ok=overwrite)
         contentFile = open(leafsPath+"index.html", "w",encoding=None)
         contentFile.write(contents)
      case 'txt':
         # info txt path
         # Write a simple txt with the name and entityID of the institution for comparison
         leafsPath = outputpath + "leafs/" + fileid + "/"
         # Write the txt to the leaf url
         Path(leafsPath).mkdir(parents=mkParents, exist_ok=overwrite)
         contentFile = open(leafsPath+"entity.txt", "w",encoding=None)
         contentFile.write(contents)      

   contentFile.close()

def parseLeaf(ra, raList, entityList, inputfile, outputpath, namespaces, format="html", baseURL = "https://example.org/", def_lang="en"):
   p("INFO: Using metadata file: " + inputfile, True) 
    
   tree = ET.parse(inputfile)
   root = tree.getroot()
   sp = root.findall("./md:EntityDescriptor[md:SPSSODescriptor]", namespaces)
   idp = root.findall("./md:EntityDescriptor[md:IDPSSODescriptor]", namespaces)

   ra_hash = raList[ra]["ra_hash"]
   ra_name = raList[ra]["ra_name"]
   ta_url = raList[ra]["ta_url"]

   for EntityDescriptor in idp:
         info = ""
         privacy = ""

         # Get entityID
         entityID = getEntityID(EntityDescriptor,namespaces)

         p("INFO: Working on: " + entityID, True)
         # Start processing SAML metadata for this entity and put that in a dict

         # Entity Categories live above IdP or SP descriptor, but ewe want to search on a per EntityID basis
         EntityCategories= root.findall(".//*[@entityID='"+entityID+"']//saml:AttributeValue", namespaces)
         ECs = getEntityCategories(EntityCategories)

         # Get hashed entityID
         cont_id = hashSHA1(entityID)

         # If an entity is already in the list of entties we do not need to process the metadata and we only need to append the TA
         if cont_id in entityList: 
            # Update TA
            updateOIDCfedMetadata(entityList[cont_id], 'authority_hints',  ta_url)
         else:

            #Get Shib MD Scope
            shibscope = getElement(EntityDescriptor,namespaces, 'shibscope','idp')
            
            # Get InformationURL
            info = getElement(EntityDescriptor,namespaces, 'informationurl','idp')

            # Get PrivacyStatementURL
            privacy = getElement(EntityDescriptor,namespaces, 'privacystatementurl','idp')

            # Get ServiceName
            serviceName = getElement(EntityDescriptor,namespaces, 'displayname','idp')

            # Get Description
            description = getElement(EntityDescriptor,namespaces, 'description','idp')

            # Get Requested Attributes
            requestedAttributes = getRequestedAttribute(EntityDescriptor,namespaces)

            # Get Organization
            orgName = getElement(EntityDescriptor,namespaces, 'organizationname','idp')
            orgURL = getElement(EntityDescriptor,namespaces, 'organizationurl','idp')
            
            # Get Contacts
            techContacts = getContacts(EntityDescriptor, namespaces, 'technical', 'json')
            suppContacts = getContacts(EntityDescriptor, namespaces, 'support', 'json')
            adminContacts = getContacts(EntityDescriptor, namespaces, 'administrative', 'json')
            securityContacts = getContacts(EntityDescriptor, namespaces, 'other', 'json')
            contacts = OrderedDict([
               ('technical', techContacts),
               ('support', suppContacts),
               ('administrative', adminContacts),
               ('security', securityContacts),
            ])

            logo = getElement(EntityDescriptor,namespaces, 'logo','idp')

            # End of processing SAML metadata for this entity 
            # Now transform that to OIDCfed metadata

            # Generate key material
            keys=mkJWK(cont_id)

            # Build LEAF JSON Dictionary
            # Take care: this dict holds the leaf private key!
            leaf = OrderedDict([
            ('id',cont_id),
            ('type', 'op'),
            ('ra',ra_hash),
            ('raName',ra_name),
            ('taURL',ta_url),
            ('resourceName',serviceName),
            ('description', description),
            ('resourceAttributes',requestedAttributes),
            ('entityID',entityID),
            ('resourceContacts',contacts), # Formatting not correct?
            ('info', info),
            ('orgName', orgName),
            ('orgURL', orgURL),
            ('logo', logo),
            ('privacy', privacy),
            ('entityCategories', ECs),
            ('keys', keys),
            ('contacts', contacts),
            ('shibscope', shibscope)
            ])     

            #Generate and Write json formatted metadata
            leafMetadata = mkOIDCfedMetadata(leaf,baseURL) 
   
            # Add leaf to entityList
            #if cont_id not in entityList: This should not happen...
            entityList[cont_id]=OrderedDict([
               ('base', leaf),
               ('metadata', leafMetadata)
            ]) 

            p("INFO: Processing "+entityID+" completed",True)

   for EntityDescriptor in sp:
      info = ""
      privacy = ""
      
      # Get entityID
      entityID = getEntityID(EntityDescriptor,namespaces)
         

      # Start processing SAML metadata for this entity and put that in a dict

      # Entity Categories live above IdP or SP descriptor, but we want to search on a per EntityID basis
      EntityCategories= root.findall(".//*[@entityID='"+entityID+"']//saml:AttributeValue", namespaces)
      ECs = getEntityCategories(EntityCategories)
      
      # Get hashed entityID
      cont_id = hashSHA1(entityID)

      # If an entity is already in the list of entties we do not need to process the metadata and we only need to append the TA
      if cont_id in entityList: 
         # Update TA
         updateOIDCfedMetadata(entityList[cont_id], 'authority_hints',  ta_url)
      else:

         # Get InformationURL
         info = getElement(EntityDescriptor,namespaces, 'informationurl','sp')

         # Get PrivacyStatementURL
         privacy = getElement(EntityDescriptor,namespaces, 'privacystatementurl','sp')

         # Get ServiceName
         serviceName = getElement(EntityDescriptor,namespaces, 'servicename','sp')

         # Get Description
         description = getElement(EntityDescriptor,namespaces, 'description','sp')

         # Get Requested Attributes
         requestedAttributes = getRequestedAttribute(EntityDescriptor,namespaces)

         # Get Organization
         orgName = getElement(EntityDescriptor,namespaces, 'organizationname','sp')

         orgURL = getElement(EntityDescriptor,namespaces, 'organizationurl','sp')

         # Get Contacts
         techContacts = getContacts(EntityDescriptor, namespaces, 'technical', 'json')
         suppContacts = getContacts(EntityDescriptor, namespaces, 'support', 'json')
         adminContacts = getContacts(EntityDescriptor, namespaces, 'administrative', 'json')
         securityContacts = getContacts(EntityDescriptor, namespaces, 'other', 'json')
         contacts = OrderedDict([
            ('technical', techContacts),
            ('support', suppContacts),
            ('administrative', adminContacts),
            ('security', securityContacts),
         ])

         logo = getElement(EntityDescriptor,namespaces, 'logo','sp')
         
         # End of processing SAML metadata for this entity 
         # Now transform that to OIDCfed metadata

         # Generate key material
         keys=mkJWK(cont_id)

         # Build LEAF JSON Dictionary
         # Take care: this dict holds the leaf private key!
         leaf = OrderedDict([
         ('id',cont_id),
         ('type', 'rp'),
         ('ra',ra_hash),
         ('raName',ra_name),
         ('taURL',ta_url),
         ('resourceName',serviceName),
         ('description', description),
         ('resourceAttributes',requestedAttributes),
         ('entityID',entityID),
         ('resourceContacts',contacts), # Formatting not correct?
         ('info', info),
         ('logo', logo),
         ('privacy', privacy),
         ('entityCategories', ECs),
         ('keys', keys)
         ])     

         #Generate and Write json formatted metadata
         leafMetadata = mkOIDCfedMetadata(leaf,baseURL) 

         # Add leaf to entityList
         #if cont_id not in entityList: This should not happen...
         entityList[cont_id]=OrderedDict([
            ('base', leaf),
            ('metadata', leafMetadata)
         ]) 

def main(argv):

   # SAML metadata handling and general io param's
   ROOTPATH='.'
   CONFIG_PATH = ROOTPATH + '/config/'
   INPUT_PATH = ROOTPATH + '/feeds/'
   OUTPUT_PATH = ROOTPATH + '/var/www/oidcfed/'
   TESTBED_PATH = ROOTPATH + '/testbed'
   OUTPUT_PATH = TESTBED_PATH + '/leafs/data/html/'
   KEYS_PATH = ROOTPATH + '/keys/'

   EDUGAIN_RA_URI = 'https://www.edugain.org'
   entityList = {}
   inputfile = None
   inputpath = INPUT_PATH
   #outputpath = OUTPUT_PATH

   ENROLLLEAFS = True
   subordinates = ["#! /bin/bash"]
   DEFAULT_LANGUAGE = "en"

   DOCKER_CONTAINER_NAME = "testbed-~~container_name~~-1"


   namespaces = {
      'xml':'http://www.w3.org/XML/1998/namespace',
      'md': 'urn:oasis:names:tc:SAML:2.0:metadata',
      'mdrpi': 'urn:oasis:names:tc:SAML:metadata:rpi',
      'shibmd': 'urn:mace:shibboleth:metadata:1.0',
      'mdattr': 'urn:oasis:names:tc:SAML:metadata:attribute',
      'saml': 'urn:oasis:names:tc:SAML:2.0:assertion',
      'ds': 'http://www.w3.org/2000/09/xmldsig#',
      'mdui': 'urn:oasis:names:tc:SAML:metadata:ui'
   }

   #OIDCfed params
   baseURL = "https://leafs.oidf.lab.surf.nl/"
   metadataURLpath = ".well-known/openid-federation/"
   
   # First load RA config
   #raConf = loadJSONconfig(CONFIG_PATH + 'RAs.json')
   edugainFedsURL = 'https://technical.edugain.org/api.php?action=list_feds_full'
   allFeds = getFeds(edugainFedsURL, INPUT_PATH)
   raConf = parseFeds(allFeds)
   
   RAs = setRAdata(raConf, INPUT_PATH, EDUGAIN_RA_URI)

   # For each RA process the entities
   for ra in RAs.keys():
      ParseRA = True
      p("INFO: Processing " + RAs[ra]["ra_name"], False)

      if RAs[ra]["ra_name"] == 'ch.switchaai' or RAs[ra]["ra_name"] == 'gb.uk-federation':
         ParseRA = True

      if ParseRA:
         # Load entity data from federation endpoint(s) and retunn me the file locations
         RAs[ra]["filepath"] = fetchMetadata(RAs[ra]["md_url"], RAs[ra]["ra_name"], INPUT_PATH)
   
         # Now loop over RAs files to extract entity metadata and work that into a json containing a 'base' entity properties as lifted from SAML 
         # And a 'metadata' structure containing the OIDCfed metadata 
         #try:
         if RAs[ra]["filepath"][0] is not None:
            parseLeaf(ra, RAs, entityList, RAs[ra]["filepath"][0], OUTPUT_PATH, namespaces, "json", baseURL, DEFAULT_LANGUAGE)
         #except:
         #   p("Could not parse leaf") 
         #   pj(RAs[ra])
      
         p(RAs[ra]["ra_name"] + " Parsed")
      else:
         p(".... Skipped", True)


   for leafID in entityList:
      leafKeys = entityList[leafID]['base']['keys']
      leafMeta = entityList[leafID]['metadata']
      leafEntityID = entityList[leafID]['base']['entityID']

      #Export and Write private key
      writeFile(exportKey(leafKeys, "private"), leafID, OUTPUT_PATH, "jwk")
      writeFile(leafMeta, leafID, OUTPUT_PATH, "json")
      htmlContent = "<h3>" + leafEntityID + "</h3><p>OIDFed Entity Configuration:<ul>" + "<li><a href='"+ entityList[leafID]['metadata']['sub'] + "/.well-known/openid-federation'>JWT</a> (Will be downloaded)</li>" + "<li><a href='"+ entityList[leafID]['metadata']['sub'] + "/entity.json' target='_blank'>JSON</a> (Opens in new window)</li>" + "</ul></p>"
      writeFile(htmlContent, leafID, OUTPUT_PATH, "html")

      #Generate and Write jwt signed metadata
      signedLeafMetadata = mkSignedOIDCfedMetadata(leafMeta, leafKeys)
      writeFile(signedLeafMetadata, leafID, OUTPUT_PATH, "jwt")

      # Enroll the entities in the federation by registering them into the TAs
      if ENROLLLEAFS:
         subordinates.append("docker exec " +DOCKER_CONTAINER_NAME.replace("~~container_name~~", entityList[leafID]['base']['raName'])+ " /tacli -c /data/config.yaml subordinates add " + entityList[leafID]['metadata']['sub'])
         #uploadMetadata(entityList[leafID]['base']['taURL'], entityList[leafID]['metadata']['sub'], entityList[leafID]['base']['type'])
         #time.sleep(5)

   write_file('\n'.join(subordinates), TESTBED_PATH+'/leaf_subordinates.sh', mkpath=False, overwrite=True)


if __name__ == "__main__":
   main(sys.argv[1:])
