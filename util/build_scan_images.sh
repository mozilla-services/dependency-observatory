#!/bin/bash

set -e

eval $(minikube -p minikube docker-env)

# build scan images
docker build --build-arg=BASE_NAME=node --build-arg=BASE_VERSION=12-buster-slim -t mozilla/dependency-observatory:node-12 ./scan_envs
docker build --build-arg=BASE_NAME=node --build-arg=BASE_VERSION=10-buster-slim -t mozilla/dependency-observatory:node-10 ./scan_envs
docker build --build-arg=BASE_NAME=rust --build-arg=BASE_VERSION=1-slim-buster -t mozilla/dependency-observatory:rust-1 ./scan_envs
