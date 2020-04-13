from datetime import datetime, timedelta
import re
from typing import Tuple

from celery import Celery
from flask import Blueprint, jsonify, make_response, request
from werkzeug.exceptions import BadRequest

import depobs.worker.tasks as tasks

scans_blueprint = api = Blueprint("scans_blueprint", __name__)


@api.errorhandler(BadRequest)
def handle_bad_request(e):
    return dict(description=e.description), 400


def validate_scored_after_ts_query_param() -> datetime:
    param_values = request.args.getlist("scored_after_ts", int)
    if len(param_values) > 1:
        raise BadRequest(description="only one scored_after_ts param supported")
    param_value = param_values[0] if len(param_values) else None
    # utcfromtimestamp might raise https://docs.python.org/3/library/exceptions.html#OverflowError
    return (
        datetime.utcfromtimestamp(param_value)
        if param_value
        else (datetime.now() - timedelta(days=90))
    )


def validate_npm_package_version_query_params() -> Tuple[str, str, str]:
    package_names = request.args.getlist("package_name", str)
    package_versions = request.args.getlist("package_version", str)
    package_managers = request.args.getlist("package_manager", str)
    if len(package_names) != 1:
        raise BadRequest(description="only one package name supported")
    if len(package_versions) > 1:
        raise BadRequest(description="only zero or one package version supported")
    if len(package_managers) > 1:
        raise BadRequest(description="only one package manager supported")

    package_name = package_names[0]
    package_version = (
        package_versions[0]
        if (len(package_versions) and package_versions[0] != "")
        else None
    )
    package_manager = package_managers[0] if len(package_managers) else "npm"

    package_name_validation_error = tasks.get_npm_package_name_validation_error(
        package_name
    )
    if package_name_validation_error is not None:
        raise BadRequest(description=str(package_name_validation_error))

    if package_version:
        package_version_validation_error = tasks.get_npm_package_version_validation_error(
            package_version
        )
        if package_version_validation_error is not None:
            raise BadRequest(description=str(package_version_validation_error))

    if package_manager != "npm":
        raise BadRequest(description="only the package manager 'npm' supported")

    return package_name, package_version, package_manager


@api.route("/scan", methods=["POST"])
def scan():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    result: celery.result.AsyncResult = tasks.scan_npm_package.delay(
        package_name, package_version
    )
    return dict(task_id=result.id)


@api.route("/build_report_tree", methods=["POST"])
def build_report_tree():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    result: celery.result.AsyncResult = tasks.build_report_tree.delay(
        (package_name, package_version)
    )
    return dict(task_id=result.id)


@api.route("/scan_then_build_report_tree", methods=["POST"])
def scan_npm_package_then_build_report_tree():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    result: celery.result.AsyncResult = tasks.scan_npm_package_then_build_report_tree.delay(
        package_name, package_version
    )
    return dict(task_id=result.id)


@api.route("/score", methods=["POST"])
def score():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    result: celery.result.AsyncResult = tasks.score_package.delay(
        package_name, package_version
    )
    return dict(task_id=result.id)
