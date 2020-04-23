#!/bin/bash

CI=${CI:-""}

if [[ "$CI" = "" ]]; then
    # requires a running api container
    docker-compose exec api coverage run -m pytest "$@"
    docker-compose exec api coverage report
    docker-compose exec api coverage html
    rm -rf htmlcov/
    docker cp dependency-observatory-api:/tmp/htmlcov/ "$(pwd)/htmlcov/"
    python -m webbrowser -t htmlcov/index.html
else
    set -v
    coverage run -m pytest
fi
