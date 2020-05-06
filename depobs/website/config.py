import os
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
        "depobs.database.models": {"handlers": ["console"], "level": "INFO"},
        "depobs.website.views": {"handlers": ["console"], "level": "INFO"},
        "depobs.website.scans": {"handlers": ["console"], "level": "INFO"},
        "depobs.worker.tasks": {"handlers": ["console"], "level": "INFO"},
        "depobs.worker.scoring": {"handlers": ["console"], "level": "INFO",},
        "depobs.scanner.clients.cratesio": {"handlers": ["console"], "level": "INFO"},
        "depobs.scanner.clients.npmsio": {"handlers": ["console"], "level": "INFO"},
        "depobs.scanner.clients.npm_registry": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "depobs.scanner.docker.images": {"handlers": ["console"], "level": "INFO"},
        "depobs.scanner.docker.containers": {"handlers": ["console"], "level": "INFO"},
        "depobs.scanner.docker.log_reader": {"handlers": ["console"], "level": "WARN"},
        "depobs.scanner.pipelines.fetch_package_data": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "depobs.scanner.pipelines.run_repo_tasks": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "depobs.scanner.pipelines.postprocess": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "depobs.scanner.pipelines.save_to_db": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}

# Flask-SQLAlchemy config
SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI", None)
SQLALCHEMY_TRACK_MODIFICATIONS = bool(
    os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS", False)
)

# try to create tables and views for depobs
INIT_DB = bool(os.environ.get("INIT_DB", False) == "1")

# Task names the web/flask app can register and run
WEB_TASK_NAMES = [
    "add",
    "build_report_tree",
    "fetch_and_save_registry_entries",
    "scan_npm_package",
    "scan_npm_package_then_build_report_tree",
]

# Celery config
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", None)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", None)

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


# depobs.scanner config

_aiohttp_args = dict(
    # User agent to user to query third party APIs
    user_agent="https://github.com/mozilla-services/dependency-observatory-scanner (foxsec+dependency+observatory@mozilla.com)",
    # aiohttp total timeout in seconds
    total_timeout=300,
    # number of simultaneous connections to open
    max_connections=10,
    # time to sleep between requests in seconds
    delay=0.5,
)


NPM_CLIENT = {
    **_aiohttp_args,
    "max_retries": 1,
    "package_batch_size": 10,
    "dry_run": False,
    # an npm registry access token for fetch_npm_registry_metadata. Defaults NPM_PAT env var. Should be read-only.
    "npm_auth_token": os.environ.get("NPM_PAT", None),
}

NPMSIO_CLIENT = {
    **_aiohttp_args,
    "max_connections": 1,
    "package_batch_size": 50,
    "dry_run": False,
}

# shared docker args for multiple tasks
_docker_args = dict(
    # pull base docker images before building them
    docker_pull=True,
    # build docker images
    docker_build=True,
    # non-default docker images to use for the task
    docker_image=[],
)

SCAN_NPM_TARBALL_ARGS = {
    **_docker_args,
    **dict(
        dry_run=False,
        language=["nodejs"],
        package_manager=["npm"],
        repo_task=["install", "list_metadata", "audit"],
    ),
}
