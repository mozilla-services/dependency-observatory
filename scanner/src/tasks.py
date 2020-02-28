import os
import sys
import re
import subprocess

from celery import Celery
from celery.exceptions import (
    SoftTimeLimitExceeded,
    TimeLimitExceeded,
    WorkerLostError,
    WorkerShutdown,
    WorkerTerminate,
)

import celeryconfig


# Create the scanner task queue
scanner = Celery('tasks', broker=os.environ["BROKER_URL"])
scanner.config_from_object(celeryconfig)

# The name must be less than or equal to 214 characters. This includes the scope for scoped packages.
# The name can’t start with a dot or an underscore.
# New packages must not have uppercase letters in the name.
# The name ends up being part of a URL, an argument on the command line, and a folder name. Therefore, the name can’t contain any non-URL-safe characters.
#
# https://docs.npmjs.com/files/package.json#name
NPM_PACKAGE_NAME_RE = re.compile(
    r"""
[@a-zA-Z0-9][\.-_@/a-zA-Z0-9]{0,213}
""",
    re.VERBOSE,
)


@scanner.task()
def add(x, y):
    return x + y


@scanner.task()
def analyze_package(package_name: str):
    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        raise ValueError(f"invalid package name {package_name!r}")

    subprocess.check_output(
        ["./bin/analyze_package.sh", package_name],
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )


def main():
    print(sys.argv)
    print(analyze_package.delay(sys.argv[1]))


if __name__ == "__main__":
    main()
