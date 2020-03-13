#!/bin/bash

# for use in the worker container; starts a worker; runs a celery task and exits
celery -A depobs.worker.tasks worker --loglevel=info &
WORKER_PID=$!
celery -A depobs.worker.tasks call depobs.worker.tasks.add --args '[2, 2]' --kwargs '{}'
sleep 1
# trigger worker shutdown after finishing the running job
kill -TERM $WORKER_PID
