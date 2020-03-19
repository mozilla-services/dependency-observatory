from datetime import datetime
from typing import Optional

from flask import abort, Response, request, send_from_directory
from werkzeug.exceptions import BadRequest, NotFound

from depobs.website import models, app
from depobs.website.scans import tasks_api, validate_npm_package_version_query_params
import depobs.worker.tasks as tasks


STANDARD_HEADERS = {
    'Access-Control-Allow-Origin' : '*'
}

app.register_blueprint(tasks_api)


class PackageReportNotFound(NotFound):
    package_name: str
    package_version: Optional[str] = None
    scored_after: Optional[datetime] = None

    def __init__(self, package_name: str, package_version: Optional[str] = None, scored_after: Optional[datetime] = None):
        self.package_name = package_name
        self.package_version = package_version
        self.scored_after = scored_after

    @property
    def description(self: NotFound) -> str:
        msg = f"PackageReport {self.package_name}"
        if self.package_version is not None:
            msg += f"@{self.package_version}"
        if self.scored_after is not None:
            msg += f"scored after {self.scored_after}"
        return msg + " not found."


def get_most_recently_scored_package_report_or_raise(package_name: str, package_version: str) -> models.PackageReport:
    "Returns a PackageReport or "
    package_report = models.get_most_recently_scored_package_report(package_name, package_version)
    if package_report is None:
        raise PackageReportNotFound(package_name=package_name, package_version=package_version)

    return package_report


@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return dict(description=e.description), 400


@app.errorhandler(PackageReportNotFound)
def handle_pakage_report_not_found(e):
    print(f"missing package report! {e}")
    package_name, package_version = e.package_name, e.package_version

    # start a task to scan the package
    result: celery.result.AsyncResult = tasks.scan_npm_package.delay(
        package_name, package_version
    )
    # NB: use transaction concurrent calls e.g. another query inserts after select
    package_report = models.insert_package_report_placeholer_or_update_task_id(
        package_name, package_version, result.id
    )
    return package_report.json_with_task(), 202


@app.route('/package', methods=["GET"])
def show_package_by_name_and_version_if_available():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    # TODO: fetch all package versions
    # TODO: parsed scored_after_s query param

    package_report = get_most_recently_scored_package_report_or_raise(package_name, package_version)
    return package_report.json_with_dependencies()


@app.route('/parents', methods=["GET"])
def get_parents_by_name_and_version():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    # TODO: fetch all package versions
    # TODO: parsed scored_after_s query param

    package_report = get_most_recently_scored_package_report_or_raise(package_name, package_version)
    return package_report.json_with_parents()


@app.after_request
def add_standard_headers_to_static_routes(response):
    response.headers.update(STANDARD_HEADERS)
    return response


@app.route('/__lbheartbeat__')
def lbheartbeat():
    return Response("badum badum", mimetype="text/plain")

@app.route('/__heartbeat__')
def heartbeat():
    return Response("badum badum", mimetype="text/plain")

@app.route('/__version__')
def version():
    return send_from_directory('/app', 'version.json')
