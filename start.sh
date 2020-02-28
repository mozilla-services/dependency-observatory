#!/bin/bash
app="dependency-observatory"
docker build -t ${app} .
docker run -d -p 5000:5000 \
  -h 0.0.0.0 \
  --name=${app} \
  -v $PWD:/app dependency-observatory flask run -h 0.0.0.0