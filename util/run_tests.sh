#!/bin/bash

# requires a running api container
docker exec -it dependency-observatory-api pytest "$@"
