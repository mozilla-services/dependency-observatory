import click
from flask import Flask
from flask.cli import AppGroup

from depobs.website.do import create_app
from depobs.worker import tasks


app = create_app()

npm_cli = AppGroup("npm")


@npm_cli.command("scan")
@click.argument("package_name", envvar="PACKAGE_USERNAME")
@click.argument("package_version", envvar="PACKAGE_VERSION")
def scan_npm_package(package_name: str, package_version: str):
    """
    Help!
    """
    tasks.scan_npm_package_then_build_report_tree(package_name, package_version)


def main():
    app.cli.add_command(npm_cli)
    app.cli.main()


if __name__ == "__main__":
    main()
