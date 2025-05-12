#! /bin/bash
cat ./tmp.yaml | sed "s/''//g" > ./docker-compose.yaml
rm ./tmp.yaml
