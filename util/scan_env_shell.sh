#!/bin/bash

set -e

# run a scan image shell on the minikube cluster
# usage: ./util/scan_env_shell.sh node-12

eval $(minikube -p minikube docker-env)
docker run -it --rm --entrypoint /bin/bash "mozilla/dependency-observatory:${1}"
