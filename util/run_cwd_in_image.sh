#!/usr/bin/env bash

# pulls a docker image, and runs the following commands with cwd mounted into /app on the image
#
# usage to get a shell:
#
# $ DOCKER_IMAGE=node:12-slim run_cwd_in_image.sh /bin/bash
# 12-slim: Pulling from library/node
# Digest: sha256:dcb63655bd32cd70ca6a6669cfa7cd10dfe3d3a2fc696924501aaad265c47f0a
# Status: Image is up to date for node:12-slim
# docker.io/library/node:12-slim
# root@b3193f712441:/app#
#
# usage passing additional arg:
#
# $ DOCKER_IMAGE=node:12-slim ./util/run_cwd_in_image.sh /bin/bash -c "pwd"
# 12-slim: Pulling from library/node
# Digest: sha256:dcb63655bd32cd70ca6a6669cfa7cd10dfe3d3a2fc696924501aaad265c47f0a
# Status: Image is up to date for node:12-slim
# docker.io/library/node:12-slim
# /app
#
# might get docker login warning for images only tagged locally:
#
# $ DOCKER_IMAGE=dep-obs/node:10 run_cwd_in_image.sh
# Using default tag: latest
# Error response from daemon: pull access denied for dep-obs/node-10, repository does not exist or may require 'docker login': denied: requested access to the resource is denied
# root@a87f88cccf7b:/app#
#
DOCKER_IMAGE=${DOCKER_IMAGE:-}

docker pull "$DOCKER_IMAGE"
docker run -it -v "$(pwd)":/app -w /app "$DOCKER_IMAGE" "$@"
