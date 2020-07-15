import click
from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext

from depobs.website.do import create_app
from depobs.worker import tasks


app = create_app()
npm_cli = AppGroup("npm")


@app.cli.command("run")
@with_appcontext
def listen_and_serve() -> None:
    """
    Run a worker process that:

    * reads tasks from the pending tasks table
    * start k8s jobs in the untrusted jobs cluster
    * subscribes to pubsub output from the running jobs
    * saves the job output
    * fetches additional data from APIs
    * score packages from the fetched data and scan results
    """
    pass


@npm_cli.command("scan")
@click.argument("package_name", envvar="PACKAGE_NAME")
@click.argument("package_version", envvar="PACKAGE_VERSION")
def scan_npm_package(package_name: str, package_version: str) -> None:
    """
    Scan and score an npm package name and version
    """
    tasks.scan_npm_package_then_build_report_tree(package_name, package_version)


@npm_cli.command("package-advisories")
@click.argument("package_name", envvar="PACKAGE_NAME")
def get_package_advisories(package_name: str) -> None:
    """
    Get GitHub Advisories for a specific package
    """
    tasks.get_github_advisories_for_package(package_name)


@npm_cli.command("advisories")
def get_ecosystem_advisories() -> None:
    """
    Get GitHub Advisories for the NPM ecosystem
    """
    tasks.get_github_advisories()


@npm_cli.command("breaches")
@click.argument("package_name", envvar="PACKAGE_NAME")
@click.argument("package_version", envvar="PACKAGE_VERSION", required=False)
def get_maintainer_breaches(package_name: str, package_version: str = None) -> None:
    """
    Get HaveIBeenPwned breaches for maintainers of a specific package
    """
    tasks.get_maintainer_breaches(package_name, package_version)


def main():
    app.cli.add_command(npm_cli)
    app.cli.main()


if __name__ == "__main__":
    main()
