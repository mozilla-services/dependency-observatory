#!/bin/bash

# requires a running api container
CI=${CI:-""}

if [[ "$CI" = "" ]]; then
    docker-compose exec api coverage run -m pytest "$@"
    docker-compose exec api coverage report
    docker-compose exec api coverage html
    docker cp dependency-observatory-api:/tmp/htmlcov/ $(pwd)/htmlcov/
    python -m webbrowser -t htmlcov/index.html
else
    coverage run -m pytest
    coverage report
    coverage html
    cp /tmp/htmlcov/ .
fi
