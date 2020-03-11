import os
import sys
import re
import subprocess
from typing import List, Tuple, Union

from celery import Celery
from celery.exceptions import (
    SoftTimeLimitExceeded,
    TimeLimitExceeded,
    WorkerLostError,
    WorkerShutdown,
    WorkerTerminate,
)

import depobs.worker.celeryconfig as celeryconfig


# The name must be less than or equal to 214 characters. This includes the scope for scoped packages.
# The name can’t start with a dot or an underscore.
# New packages must not have uppercase letters in the name.
# The name ends up being part of a URL, an argument on the command line, and a folder name. Therefore, the name can’t contain any non-URL-safe characters.
#
# https://docs.npmjs.com/files/package.json#name
NPM_PACKAGE_NAME_RE = re.compile(
    r"""[@a-zA-Z0-9][\.-_@/a-zA-Z0-9]{0,213}""",
    re.VERBOSE,
)

# TODO: move to config file?
# scans the worker can run in tuples with the format:
#
# (
#   <scanner container/docker image name (type str)>,
#   [<arg or validation regex (type Union[str, re.Pattern])>]*
# )
# the images already be built/pulled/present on the worker node
SCANS: List[Tuple[str, List[Union[str, re.Pattern]]]] = [
    ("mozilla/dependencyscan:latest", ["analyze_package.sh", NPM_PACKAGE_NAME_RE])
]

# Create the scanner task queue
scanner = Celery("tasks", broker=os.environ["CELERY_BROKER_URL"])
scanner.config_from_object(celeryconfig)


@scanner.task()
def add(x, y):
    return x + y


@scanner.task()
def run_image(
    requested_image_name: str, requested_args: List[Union[str, re.Pattern]] = None
):
    if requested_args is None:
        requested_args = []

    try:
        scan_image_name, scan_arg_patterns = next(
            scan for scan in SCANS if scan[0] == requested_image_name
        )
    except StopIteration:
        raise ValueError(f"invalid scanner docker image name {requested_image_name}")

    command = [
        "docker",
        "run",
        "-e",
        f"DB_URL={os.environ['DATABASE_URI']}",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "--rm",
        scan_image_name,
    ]

    i = 0
    for scan_arg_pattern in scan_arg_patterns:
        # add constant args to the command
        if isinstance(scan_arg_pattern, str):
            command.append(scan_arg_pattern)
            continue

        assert isinstance(scan_arg_pattern, re.Pattern)
        if len(requested_args) < i:
            raise ValueError(f"missing arg {i}")

        if not re.match(scan_arg_pattern, requested_args[i]):
            raise ValueError(
                f"invalid arg {i} {requested_args[i]!r} did not match {scan_arg_pattern.pattern!r}"
            )
        command.append(requested_args[i])
        i += 1

    return subprocess.run(command, encoding="utf-8", capture_output=True)
