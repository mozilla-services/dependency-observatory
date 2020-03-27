#!/bin/bash

# for use in the worker container; starts a worker; runs a celery task
# and exits; tailing worker logs
#
# example usage: call_task_with_result.sh add --args "[2,2]" --kwargs "{}"
#
task_name="$1"
shift 1
task_args_and_kwargs="$@"
celery -A depobs.worker.tasks worker --loglevel=info &
WORKER_PID=$!
echo "running: celery -A depobs.worker.tasks call depobs.worker.tasks.${task_name} $task_args_and_kwargs"
celery -A depobs.worker.tasks call "depobs.worker.tasks.${task_name}" $task_args_and_kwargs
sleep 1
# trigger worker shutdown after finishing the running job
kill -TERM $WORKER_PID
