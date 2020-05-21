#!/bin/bash

# requires a running api container
docker exec -u 0 -it dependency-observatory-api flask db "$@"
