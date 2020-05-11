#!/bin/bash

CI=${CI:-""}
CONTAINER_NAME=${CONTAINER_NAME:-"dependency-observatory-api"}

rm -rf htmlcov/
docker exec -it "$CONTAINER_NAME" coverage run -m pytest "$@"
docker exec -it "$CONTAINER_NAME" coverage report
docker exec -it "$CONTAINER_NAME" coverage html
docker cp dependency-observatory-api:/tmp/htmlcov/ "$(pwd)/htmlcov/"

if [[ "$CI" = "" ]]; then
    python -m webbrowser -t htmlcov/index.html
fi
