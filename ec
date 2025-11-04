#! /bin/bash

#/usr/bin/python3 ./mkOIDfedEntityConfig.py
docker run -it --rm --name my-running-script -v "$PWD":/usr/src/myapp -w /usr/src/myapp saml-oidf /usr/bin/python3 mkOIDfedEntityConfig.py
