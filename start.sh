#!/bin/bash
app="dependency-observatory"
docker build -t ${app} .
docker run -d -p 8000:8000 \
  -h 0.0.0.0 \
  --name=${app} \
  -v $PWD:/app dependency-observatory flask run -h 0.0.0.0 --port 8000