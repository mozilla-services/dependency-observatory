#!/bin/bash
set -e

# takes an optional 'migrate' command then the process to exec of
# 'web', 'worker', or 'worker-dev'

DB_REVISION=${DB_REVISION:-"head"}
if [ "$1" = 'migrate' ]; then
    flask db upgrade "$DB_REVISION"
    shift
fi
if [ "$1" = 'print-db-revision' ]; then
    flask db show
    shift
fi

if [ "$1" = 'web' ]; then
    gunicorn -w 4 "depobs.website.do:create_app()"
elif [ "$1" = 'web-dev' ]; then
    python depobs/website/do.py
elif [ "$1" = 'worker' ]; then
    python depobs/worker/main.py
else
    echo "got unrecognized command:" "$1"
    exit 1
fi
