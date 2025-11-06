#! /bin/bash

#/usr/bin/python3 ./mkOIDfedEntityConfig.py
docker build -t oidf-testbed .
docker run -it --rm --name mk-oidf-testbed -v "$PWD":/app -w /app oidf-testbed /usr/bin/python3 mkOIDfedEntityConfig.py
