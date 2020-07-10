import click
from flask import Flask
from flask.cli import AppGroup

from depobs.website.do import create_app
from depobs.worker import tasks


app = create_app()

npm_cli = AppGroup("npm")


@npm_cli.command("scan")
@click.argument("package_name", envvar="PACKAGE_NAME")
@click.argument("package_version", envvar="PACKAGE_VERSION")
def scan_npm_package(package_name: str, package_version: str) -> None:
    """
    Help!
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


def main():
    app.cli.add_command(npm_cli)
    app.cli.main()


if __name__ == "__main__":
    main()
