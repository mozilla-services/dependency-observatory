import re

from celery import Celery
from flask import Blueprint, jsonify, make_response, request

import depobs.worker.tasks as tasks

scans_api = api = Blueprint('scans_api', __name__)


@api.route('/scan', methods=['POST'])
def scan():
    package_names = request.args.getlist('package_name', str)
    if len(package_names) > 1:
        return dict(error="only one package name supported"), 400

    if not re.match(tasks.NPM_PACKAGE_NAME_RE, package_names[0]):
        return dict(error=f"package name did not match {tasks.NPM_PACKAGE_NAME_RE.pattern!r}"), 400

    package_managers = request.args.getlist('package_manager', str)
    if len(package_managers) > 1:
        return dict(error="only one package manager supported"), 400

    if package_managers[0] != 'npm':
        return dict(error="only package manager 'npm' supported at this time"), 400

    result: celery.result.AsyncResult = tasks.run_image.delay("mozilla/dependencyscan:latest", package_names[0])
    return dict(task_id=result.id)
