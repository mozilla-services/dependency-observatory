#!/bin/bash
set -e

# takes an optional 'migrate' and 'print-db-revision' command then
# runs starts a server for 'web', 'web-dev' or for 'worker' runs the
# flask command to completion

PROCS=${PROCS:-"4"}
THREADS=${THREADS:-"1"}


DB_REVISION=${DB_REVISION:-"head"}
if [ "$1" = 'migrate' ]; then
    flask db upgrade "$DB_REVISION"
    shift
fi
if [ "$1" = 'print-db-revision' ]; then
    flask db show
    shift
fi
if [ "$1" = 'init-gcloud-creds' ]; then
    # populate kube config
    gcloud container clusters get-credentials "$JOBS_CLUSTER_NAME" --region "$JOBS_CLUSTER_REGION"
    shift
fi

if [ "$1" = 'web' ]; then
    PROCS="$PROCS" THREADS="$THREADS" uwsgi --ini /app/uwsgi.ini
elif [ "$1" = 'web-dev' ]; then
    python depobs/website/do.py
elif [ "$1" = 'worker' ]; then
    shift
    python depobs/worker/main.py "$@"
else
    echo "got unrecognized command:" "$1"
    exit 1
fi
