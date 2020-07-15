#!/bin/bash

set -e

eval $(minikube -p minikube docker-env)

# build the combined api and worker image
./util/write_version_json.sh > version.json
docker build -t mozilla/dependency-observatory:latest .

# update deployments
kubectl set image deployments.app/api dependency-observatory-api=mozilla/dependency-observatory:latest
kubectl set image deployments.app/worker dependency-observatory-worker=mozilla/dependency-observatory:latest

# redeploy
kubectl rollout restart deployment api
kubectl rollout restart deployment worker
kubectl rollout status deployment api
kubectl rollout status deployment worker
