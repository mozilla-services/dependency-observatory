#!/bin/bash

# requires a running api container
# TODO: resolve timestamp mismatches i.e. './util/format_diff.sh | patch -f' should work
docker-compose exec api black --config pyproject.toml -q --diff . "$@"
