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
        "depobs.clients.cratesio": {"handlers": ["console"], "level": "INFO"},
        "depobs.clients.github": {"handlers": ["console"], "level": "INFO"},
        "depobs.clients.npmsio": {"handlers": ["console"], "level": "INFO"},
        "depobs.clients.npm_registry": {"handlers": ["console"], "level": "INFO",},
        "depobs.database.models": {"handlers": ["console"], "level": "INFO"},
        "depobs.database.serializers": {"handlers": ["console"], "level": "INFO"},
        "depobs.docker.containers": {"handlers": ["console"], "level": "INFO"},
        "depobs.docker.log_reader": {"handlers": ["console"], "level": "WARN"},
        "depobs.website.views": {"handlers": ["console"], "level": "INFO"},
        "depobs.website.scans": {"handlers": ["console"], "level": "INFO"},
        "depobs.website.score_details.blueprint": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "depobs.worker.tasks": {"handlers": ["console"], "level": "INFO"},
        "depobs.worker.scoring": {"handlers": ["console"], "level": "INFO",},
        "depobs.scanner.repo_tasks": {"handlers": ["console"], "level": "INFO",},
    },
}

# Flask-SQLAlchemy config
SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI", None)
SQLALCHEMY_TRACK_MODIFICATIONS = bool(
    os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS", False)
)

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
    # time to sleep between requests in seconds
    delay=0.5,
    # don't hit the third part API just print intended actions
    dry_run=False,
    # number of simultaneous connections to open
    max_connections=10,
    # number of times to retry requests
    max_retries=1,
    # number of packages to fetch in once request (for APIs that support it)
    package_batch_size=1,
    # aiohttp total timeout in seconds
    total_timeout=300,
    # user agent to use to query third party APIs
    user_agent="https://github.com/mozilla-services/dependency-observatory-scanner (foxsec+dependency+observatory@mozilla.com)",
)


NPM_CLIENT = {
    **_aiohttp_args,
    # use second dict call to workaround update typerror with line above
    # refs: https://github.com/python/mypy/issues/1430
    **dict(
        package_batch_size=10,
        # an npm registry access token for fetch_npm_registry_metadata. Defaults NPM_PAT env var. Should be read-only.
        npm_auth_token=os.environ.get("NPM_PAT", None),
    ),
}

NPMSIO_CLIENT = {**_aiohttp_args, **dict(max_connections=1, package_batch_size=50,)}

GITHUB_CLIENT = {
    **_aiohttp_args,
    # use second dict call to workaround update typerror with line above
    # refs: https://github.com/python/mypy/issues/1430
    **dict(
        # A github personal access token. Defaults GITHUB_PAT env var. It should
        # have most of the scopes from
        # https://developer.github.com/v4/guides/forming-calls/#authenticating-with-graphql
        github_auth_token=os.environ.get("GITHUB_PAT", None),
        # accept headers to add (e.g. to opt into preview APIs)
        github_accept_headers=[
            # https://developer.github.com/v4/previews/#access-to-a-repositories-dependency-graph
            "application/vnd.github.hawkgirl-preview+json",
            # https://developer.github.com/v4/previews/#github-packages
            "application/vnd.github.packages-preview+json",
        ],
        # the number of concurrent workers to run github requests
        github_workers=3,
        # github query types to fetch. When empty defaults to all query types.
        github_query_type=[],
        # number of github repo langs to fetch with each request
        github_repo_langs_page_size=25,
        # number of github repo dep manifests to fetch with each request (defaults to 1)
        github_repo_dep_manifests_page_size=1,
        # number of github repo deps for a manifest to fetch with each request (defaults to 100)
        github_repo_dep_manifest_deps_page_size=100,
        # number of github repo vuln alerts to fetch with each request (defaults to 25)
        github_repo_vuln_alerts_page_size=25,
        # number of github repo vulns per alerts to fetch with each request (defaults to 25)
        github_repo_vuln_alert_vulns_page_size=25,
        # frequency in seconds to check whether worker queues are empty and quit (defaults to 3)
        github_poll_seconds=3,
        # max times to retry a query with jitter and exponential backoff (defaults to 12). Ignores 404s and graphql not found errors
        github_max_retries=12,
    ),
}

# shared docker args for multiple tasks
_docker_args = dict(
    # non-default docker images to use for the task
    docker_images=[],
    # Print commands we would run and their context, but don't run them
    dry_run=False,
)

SCAN_NPM_TARBALL_ARGS = {
    **_docker_args,
    **dict(
        languages=["nodejs"],
        package_managers=["npm"],
        repo_tasks=["install", "list_metadata", "audit"],
    ),
}
