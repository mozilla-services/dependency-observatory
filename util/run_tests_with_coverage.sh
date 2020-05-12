#!/bin/bash

CI=${CI:-""}
CONTAINER_NAME=${CONTAINER_NAME:-"dependency-observatory-api"}

rm -rf htmlcov/

# copy tests and tes config over since CI uses built images and doesn't mount . to app
if [[ ! "$CI" = "" ]]; then
    docker cp setup.cfg "$CONTAINER_NAME:/app"
    docker cp pyproject.toml "$CONTAINER_NAME:/app"
    docker cp tests/ "$CONTAINER_NAME:/app/tests"
fi
docker exec -it -e PYTHONDONTWRITEBYTECODE=1 "$CONTAINER_NAME" coverage run -m pytest "$@"
docker exec -it "$CONTAINER_NAME" coverage report
docker exec -it "$CONTAINER_NAME" coverage html
docker cp dependency-observatory-api:/tmp/htmlcov/ "$(pwd)/htmlcov/"

if [[ "$CI" = "" ]]; then
    python -m webbrowser -t htmlcov/index.html
fi
