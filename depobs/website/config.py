import sys


LOGGING = {
    "version": 1,
    "formatters": {
        "text": {
            "format": "%(name)s [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {"()": "dockerflow.logging.JsonLogFormatter", "logger_name": "depobs"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": sys.stdout,
        }
    },
    "loggers": {
        "do": {"handlers": ["console"], "level": "DEBUG"},
        "request.summary": {"handlers": ["console"], "level": "INFO"},
    },
}


# Set the Celery task queue
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_IGNORE_RESULTS = True
CELERY_REDIRECT_STDOUTS_LEVEL = "WARNING"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"

# report status as ‘started’ when the task is executed by a worker
CELERY_TASK_TRACK_STARTED = True

CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Whether to store the task return values or not (tombstones).
#
# https://docs.celeryproject.org/en/stable/userguide/configuration.html#task-ignore-result
CELERY_TASK_IGNORE_RESULT = True

# If set, the worker stores all task errors in the result store even if Task.ignore_result is on.
#
# https://docs.celeryproject.org/en/stable/userguide/configuration.html#task-store-errors-even-if-ignored
CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True

# Send task-related events so that tasks can be monitored using tools like flower. Sets the default value for the workers -E argument.
CELERY_WORKER_SEND_TASK_EVENTS = True

# If enabled, a task-sent event will be sent for every task so tasks can be tracked before they’re consumed by a worker.
CELERY_TASK_SEND_SENT_EVENT = True

# in seconds
CELERYD_TASK_SOFT_TIME_LIMIT = 1800
CELERYD_TASK_TIME_LIMIT = 3600
