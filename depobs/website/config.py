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
        "depobs.website.views": {"handlers": ["console"], "level": "INFO"},
        "depobs.worker.k8s": {"handlers": ["console"], "level": "INFO",},
        "depobs.worker.scoring": {"handlers": ["console"], "level": "INFO",},
        "depobs.worker.tasks": {"handlers": ["console"], "level": "INFO"},
    },
}

# Flask-SQLAlchemy config
SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI", None)
SQLALCHEMY_TRACK_MODIFICATIONS = bool(
    os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS", False)
)

DEFAULT_SCORED_AFTER_DAYS = 365 * 10

DEFAULT_APP_NAMESPACE = "default"

# k8s job configs the flask app can run
WEB_JOB_CONFIGS = {
    "scan_score_npm_package": dict(
        namespace=DEFAULT_APP_NAMESPACE,
        image_name="mozilla/dependency-observatory:latest",
        base_args=["worker", "npm", "scan"],
        env={
            k: os.environ[k]
            for k in ["FLASK_APP", "FLASK_ENV", "SQLALCHEMY_DATABASE_URI"]
            if k in os.environ
        },
        service_account_name="job-runner",
    )
}


# depobs http client config

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
    user_agent="https://github.com/mozilla-services/dependency-observatory (foxsec+dependency+observatory@mozilla.com)",
)


NPM_CLIENT = {
    **_aiohttp_args,
    # use second dict call to workaround update typerror with line above
    # refs: https://github.com/python/mypy/issues/1430
    **dict(
        base_url=os.environ.get("NPM_BASE_URL", "https://registry.npmjs.com/"),
        package_batch_size=10,
        # an npm registry access token for fetch_npm_registry_metadata. Defaults NPM_PAT env var. Should be read-only.
        npm_auth_token=os.environ.get("NPM_PAT", None),
    ),
}

NPMSIO_CLIENT = {
    **_aiohttp_args,
    **dict(
        base_url=os.environ.get("NPMSIO_BASE_URL", "https://api.npms.io/v2/"),
        max_connections=1,
        package_batch_size=50,
    ),
}

GITHUB_CLIENT = {
    **_aiohttp_args,
    # use second dict call to workaround update typerror with line above
    # refs: https://github.com/python/mypy/issues/1430
    **dict(
        base_url=os.environ.get("GITHUB_BASE_URL", "https://api.github.com/graphql"),
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

SCAN_NPM_TARBALL_ARGS = dict(
    language="nodejs",
    package_manager="npm",
    namespace="default",
    image_name="mozilla/dependency-observatory:node-12",
    repo_tasks=["write_manifest", "install", "list_metadata", "audit"],
    service_account_name="default",
)
