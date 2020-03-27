#!/bin/bash

# celery worker that runs one celery task in the worker and exits
#
# example usage: call_task_with_result_in_worker.sh add --args "[2,2]" --kwargs "{}"
#
docker-compose run -u 10001 worker /app/util/call_task_with_result.sh "$@"
