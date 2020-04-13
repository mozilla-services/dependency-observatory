#!/bin/bash

# requires a running api container
docker-compose exec api black -t py38 --diff /app "$@"
