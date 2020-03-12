import os
import sys
import re
import subprocess
from typing import List, Tuple, Union, Optional
import logging

from celery import Celery
from celery.exceptions import (
    SoftTimeLimitExceeded,
    TimeLimitExceeded,
    WorkerLostError,
    WorkerShutdown,
    WorkerTerminate,
)

import depobs.worker.celeryconfig as celeryconfig

log = logging.getLogger("depobs.worker")
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

# Create the scanner task queue
scanner = Celery("tasks", broker=os.environ["CELERY_BROKER_URL"])
scanner.config_from_object(celeryconfig)


# The name must be less than or equal to 214 characters. This includes the scope for scoped packages.
# The name can’t start with a dot or an underscore.
# New packages must not have uppercase letters in the name.
# The name ends up being part of a URL, an argument on the command line, and a folder name. Therefore, the name can’t contain any non-URL-safe characters.
#
# https://docs.npmjs.com/files/package.json#name
NPM_PACKAGE_NAME_RE = re.compile(
    r"""[@a-zA-Z0-9][\.-_@/a-zA-Z0-9]{0,213}""", re.VERBOSE,
)


def get_npm_package_name_validation_error(package_name: str) -> Optional[Exception]:
    """returns an Exception if package name is invalid or None if it is valid"""
    if not isinstance(package_name, str):
        return Exception("Invalid NPM package name. Must be a str.")

    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        return Exception(
            f"Invalid NPM package name. Must match {NPM_PACKAGE_NAME_RE.pattern!r}"
        )

    return None


# Version must be parseable by node-semver, which is bundled with npm as a dependency.
#
# https://docs.npmjs.com/files/package.json#version
#
# https://docs.npmjs.com/misc/semver#versions
NPM_PACKAGE_VERSION_RE = re.compile(
    r"""(=v)?           # strip leading = and v
[0-9]+\.[0-9]+\.[0-9]+  # major minor and patch versions (TODO: check if positive ints)
[-]?[-\.0-9A-Za-z]*       # optional pre-release version e.g. -alpha.1 (TODO: split out identifiers)
[+]?[-\.0-9A-Za-z]*       # optional build metadata e.g. +exp.sha.5114f85
""",
    re.VERBOSE,
)


def get_npm_package_version_validation_error(package_name: str) -> Optional[Exception]:
    """returns an Exception if package version is invalid or None if it is valid"""
    if not isinstance(package_name, str):
        return Exception("Invalid NPM package version. Must be a str.")

    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        return Exception(
            f"Invalid NPM package version. Must match {NPM_PACKAGE_VERSION_RE.pattern!r}"
        )

    return None


@scanner.task()
def add(x, y):
    return x + y


@scanner.task()
def scan_npm_package(
    package_name: str, package_version: Optional[str] = None
) -> Optional[Exception]:
    package_name_validation_error = get_npm_package_name_validation_error(package_name)
    if package_name_validation_error is not None:
        return package_name_validation_error

    package_version_validation_error = get_npm_package_version_validation_error(
        package_version
    )
    if package_version_validation_error is not None:
        return package_version_validation_error

    # mozilla/dependencyscan:latest must already be built/pulled/otherwise
    # present on the worker node
    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        f"DB_URL={os.environ['DATABASE_URI']}",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "mozilla/dependencyscan:latest",
        "analyze_package.sh",
        package_name,
    ]
    if package_version:
        command.append(package_version)

    log.info(f"running {command} for package_name {package_name}@{package_version}")
    return subprocess.run(command, encoding="utf-8", capture_output=True)
