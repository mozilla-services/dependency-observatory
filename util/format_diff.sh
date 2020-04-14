#!/bin/bash

# requires a running api container
docker-compose exec api black --config pyproject.toml --diff /app "$@"
