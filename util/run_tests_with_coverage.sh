#!/bin/bash

# requires a running api container
docker-compose exec api coverage run -m pytest \
	       -p no:cacheprovider \
	       -o 'filterwarnings=ignore:"@coroutine" decorator is deprecated.*:DeprecationWarning' \
	       "$@"
docker-compose exec api coverage report
docker-compose exec api coverage html
docker cp dependency-observatory-api:/tmp/htmlcov/ $(pwd)/htmlcov/
python -m webbrowser -t htmlcov/index.html
