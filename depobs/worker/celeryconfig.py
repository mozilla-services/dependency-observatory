# Set the Celery task queue
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_IGNORE_RESULTS = True
CELERY_REDIRECT_STDOUTS_LEVEL = "WARNING"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"

# report status as ‘started’ when the task is executed by a worker
CELERY_TASK_TRACK_STARTED = True

CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Send task-related events so that tasks can be monitored using tools like flower. Sets the default value for the workers -E argument.
CELERY_WORKER_SEND_TASK_EVENTS = True

# If enabled, a task-sent event will be sent for every task so tasks can be tracked before they’re consumed by a worker.
CELERY_TASK_SEND_SENT_EVENT = True

# in seconds
CELERYD_TASK_SOFT_TIME_LIMIT = 1800
CELERYD_TASK_TIME_LIMIT = 3600
