import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List

import click
from flask import Flask
from flask.cli import AppGroup, with_appcontext

from depobs.database import models
from depobs.website.do import create_app
from depobs.worker.background_task_runner import run_background_tasks
from depobs.worker.tasks.start_scan import (
    start_scan,
    start_next_scan,
)
from depobs.worker.tasks.finish_scan import (
    finish_scan,
    finish_next_scan,
)
from depobs.worker.tasks.get_github_advisories import (
    get_github_advisories,
    get_github_advisories_for_package,
)
from depobs.worker.tasks.get_maintainer_hibp_breaches import get_maintainer_breaches
from depobs.worker.tasks.save_pubsub_messages import save_pubsub


log = logging.getLogger(__name__)

app = create_app()
npm_cli = AppGroup("npm")

TASKS: Dict[str, Callable[[Flask, int], Coroutine[Any, Any, None]]] = {
    "save_pubsub": save_pubsub,
    "start_next_scan": start_next_scan,
    "finish_next_scan": finish_next_scan,
}


@app.cli.command("run")
@click.option(
    "--task-name",
    required=True,
    type=click.Choice(TASKS.keys()),
    multiple=True,
)
@with_appcontext
def listen_and_run(task_name: List[str]) -> None:
    """
    Run one or more background tasks
    """
    log.info(f"starting background tasks: {task_name}")
    asyncio.run(run_background_tasks(app, [TASKS[name] for name in task_name]))


@npm_cli.command("scan")
@click.argument("package_name", envvar="PACKAGE_NAME")
@click.argument("package_version", envvar="PACKAGE_VERSION")
@with_appcontext
def scan_npm_package(package_name: str, package_version: str) -> None:
    """
    Scan and score an npm package name and version
    """
    scan = models.save_scan_with_status(
        models.package_name_and_version_to_scan(package_name, package_version),
        models.ScanStatusEnum["queued"],
    )
    log.info(f"running npm package scan with id {scan.id}")
    asyncio.run(start_scan(scan))
    log.info(f"started npm package scan")
    while True:
        asyncio.run(finish_scan(scan))
        log.info("waiting for scan to finish")
        time.sleep(3)


@npm_cli.command("package-advisories")
@click.argument("package_name", envvar="PACKAGE_NAME")
@with_appcontext
def get_package_advisories(package_name: str) -> None:
    """
    Get GitHub Advisories for a specific package
    """
    get_github_advisories_for_package(package_name)


@npm_cli.command("advisories")
@with_appcontext
def get_ecosystem_advisories() -> None:
    """
    Get GitHub Advisories for the NPM ecosystem
    """
    get_github_advisories()


@npm_cli.command("breaches")
@click.argument("package_name", envvar="PACKAGE_NAME")
@click.argument("package_version", envvar="PACKAGE_VERSION", required=False)
@with_appcontext
def get_maintainer_hibp_breaches(
    package_name: str, package_version: str = None
) -> None:
    """
    Get HaveIBeenPwned breaches for maintainers of a specific package
    """
    get_maintainer_breaches(package_name, package_version)


def main():
    app.cli.add_command(npm_cli)
    app.cli.main()


if __name__ == "__main__":
    main()
