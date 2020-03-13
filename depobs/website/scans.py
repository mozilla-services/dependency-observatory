import re

from celery import Celery
from flask import Blueprint, jsonify, make_response, request

import depobs.worker.tasks as tasks

tasks_api = api = Blueprint("tasks_api", __name__)


@api.route("/scan", methods=["POST"])
def scan():
    package_names = request.args.getlist("package_name", str)
    package_versions = request.args.getlist("package_version", str)
    package_managers = request.args.getlist("package_manager", str)
    if len(package_names) > 1:
        return dict(error="only one package name supported"), 400
    if len(package_versions) > 1:
        return dict(error="only zero or one package version supported"), 400
    if len(package_managers) > 1:
        return dict(error="only one package manager supported"), 400

    package_name = package_names[0]
    package_version = package_versions[0] if len(package_versions) else None
    package_manager = package_managers[0] if len(package_managers) else "npm"

    package_name_validation_error = tasks.get_npm_package_name_validation_error(
        package_name
    )
    if package_name_validation_error is not None:
        return dict(error=validation_error), 400

    if package_version:
        package_version_validation_error = tasks.get_npm_package_version_validation_error(
            package_version
        )
        if package_version_validation_error is not None:
            return package_version_validation_error, 400

    if package_manager != "npm":
        return dict(error="only the package manager 'npm' supported"), 400

    result: celery.result.AsyncResult = tasks.scan_npm_package.delay(
        package_name, package_version
    )
    return dict(task_id=result.id)
