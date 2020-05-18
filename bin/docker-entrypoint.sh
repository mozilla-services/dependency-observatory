#!/bin/bash
set -e

if [ "$1" = 'web' ]; then
    python depobs/website/do.py
elif [ "$1" = 'worker' ]; then
    celery --task-events -A depobs.worker.tasks worker --loglevel=info
elif [ "$1" = 'worker-dev' ]; then
    celery --task-events --purge -c 1 -A depobs.worker.tasks worker --loglevel=debug
fi
