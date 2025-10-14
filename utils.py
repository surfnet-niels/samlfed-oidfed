##################################################################################################################################
#
# Config and logs handling functions
#
##################################################################################################################################
import json
import datetime
import json
import yaml
import os
import time
import urllib.request
from pathlib import Path

def loadJSON(json_file):
   with open(json_file) as json_file:
     return json.load(json_file)

def p(message, writetolog=True):
   if writetolog:
      write_log(message)
   else:
      print(message)
    
def pj(the_json, writetolog=True):
    p(json.dumps(the_json, indent=4, sort_keys=False), writetolog)

def write_log(message):
   datestamp = (datetime.datetime.now()).strftime("%Y-%m-%d")
   timestamp = (datetime.datetime.now()).strftime("%Y-%m-%d %X")
   f = open("./logs/" + datestamp + "_testbed.log", "a")
   f.write(timestamp +" "+ message+"\n")
   f.close()

def write_file(contents, filepath, mkpath=True, overwrite=False, writetolog=True, type='txt'):
   p("[INFO] Writing file: " + filepath, writetolog)
   
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
    p("ERROR: Could not download URL: " + url)
    return False
  
def safeFileName(name):
   return name.replace('https://','').replace('http://','').replace('/','').replace('.','_')