#!/bin/bash
set -e

# takes an optional 'migrate' command then the process to exec of
# 'web', 'worker', or 'worker-dev'

DB_REVISION=${DB_REVISION:-"head"}
if [ "$1" = 'migrate' ]; then
    flask db upgrade "$DB_REVISION"
    shift
fi

flask db show

if [ "$1" = 'web' ]; then
    python depobs/website/do.py
elif [ "$1" = 'worker' ]; then
    celery --task-events -A depobs.worker.tasks worker --loglevel=info
elif [ "$1" = 'worker-dev' ]; then
    celery --task-events --purge -c 1 -A depobs.worker.tasks worker --loglevel=debug
else
    echo "got unrecognized command:" "$1"
    exit 1
fi
