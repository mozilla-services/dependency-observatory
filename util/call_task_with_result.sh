#!/bin/bash

# for use in the worker container; starts a worker; runs a celery task and exits
celery -A depobs.worker.tasks worker --loglevel=info &
WORKER_PID=$!
celery -A depobs.worker.tasks call depobs.worker.tasks.score_package --args '["@hapi/topo", "3.6.0"]' --kwargs '{}'
sleep 1
# trigger worker shutdown after finishing the running job
kill -TERM $WORKER_PID
