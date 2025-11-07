#!/usr/bin/env python3 
#-*- coding: utf-8 -*-

import os
import json
import argparse
from dotenv import load_dotenv

def load_env_vars(env_file=".env"):
    env_vars = {}
    if os.path.exists(env_file):
        load_dotenv(env_file)
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _ = line.split("=", 1)
                    env_vars[key.lower()] = os.getenv(key)
    return env_vars

def merge_env_into_template(template, env_vars):
    for key in template:
        if key in env_vars:
            template[key] = env_vars[key]
    return template

def main():
    parser = argparse.ArgumentParser(description="Convert .env to JSON config with optional template merging.")
    parser.add_argument("-o", required=True, help="Output JSON file name")
    parser.add_argument("-i", required=False, help="Optional name of env file (Defaults to .env)", default=".env")
    parser.add_argument("-t", required=False, help="Optional JSON template file")

    args = parser.parse_args()

    env_vars = load_env_vars(args.i)
    print(env_vars)

    if args.t and os.path.exists(args.t):
        with open(args.t, "r") as tmpl:
            template_data = json.load(tmpl)
        final_data = merge_env_into_template(template_data, env_vars)
    else:
        final_data = env_vars

    with open(args.o, "w") as out:
        json.dump(final_data, out, indent=4)

    print(f"✅ Configuration written to: {args.o}")

if __name__ == "__main__":
    main()

