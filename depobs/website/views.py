from datetime import datetime
from typing import Dict, Optional

from flask import abort, Blueprint, Response, request, send_from_directory
import graphviz
from werkzeug.exceptions import BadRequest, NotFound

from depobs.website import models
from depobs.website.scans import (
    validate_npm_package_version_query_params,
    validate_scored_after_ts_query_param,
)
import depobs.worker.tasks as tasks

STANDARD_HEADERS = {"Access-Control-Allow-Origin": "*"}

views_blueprint = api = Blueprint("views_blueprint", __name__)


class PackageReportNotFound(NotFound):
    package_name: str
    package_version: Optional[str] = None
    scored_after: Optional[datetime] = None

    def __init__(
        self,
        package_name: str,
        package_version: Optional[str] = None,
        scored_after: Optional[datetime] = None,
    ):
        self.package_name = package_name
        self.package_version = package_version
        self.scored_after = scored_after

    @property
    def description(self) -> str:
        msg = f"PackageReport {self.package_name}"
        if self.package_version is not None:
            msg += f"@{self.package_version}"
        if self.scored_after is not None:
            msg += f"scored after {self.scored_after}"
        return msg + " not found."


def get_most_recently_scored_package_report_or_raise(
    package_name: str, package_version: str, scored_after: datetime
) -> models.PackageReport:
    "Returns a PackageReport or raises a PackageReportNotFound exception"
    package_report = models.get_most_recently_scored_package_report(
        package_name, package_version, scored_after
    )
    if package_report is None:
        raise PackageReportNotFound(
            package_name=package_name,
            package_version=package_version,
            scored_after=scored_after,
        )

    return package_report


@api.errorhandler(BadRequest)
def handle_bad_request(e):
    return dict(description=e.description), 400


@api.errorhandler(PackageReportNotFound)
def handle_package_report_not_found(e):
    package_name, package_version = e.package_name, e.package_version

    # Is there a placeholder entry?
    package_report = models.get_placeholder_entry(package_name, package_version)
    if package_report:
        if package_report.status == "error":
            return package_report.report_json, 500
        return package_report.report_json, 202

    if not tasks.check_npm_package_exists(package_name, package_version):
        return (
            dict(
                description=f"{e.description} Unable to find package on npm registry and npms.io."
            ),
            404,
        )

    # start a task to scan the package
    result: celery.result.AsyncResult = tasks.scan_npm_package_then_build_report_tree.delay(
        package_name, package_version
    )

    # NB: use transaction concurrent calls e.g. another query inserts after select
    package_report = models.insert_package_report_placeholder_or_update_task_id(
        package_name, package_version, result.id
    )
    return package_report.report_json, 202


@api.route("/package", methods=["GET"])
def show_package_by_name_and_version_if_available() -> Dict:
    scored_after = validate_scored_after_ts_query_param()
    package_name, package_version, _ = validate_npm_package_version_query_params()
    # TODO: fetch all package versions

    package_report = get_most_recently_scored_package_report_or_raise(
        package_name, package_version, scored_after
    )
    return package_report.json_with_dependencies()


@api.route("/parents", methods=["GET"])
def get_parents_by_name_and_version() -> Dict:
    scored_after = validate_scored_after_ts_query_param()
    package_name, package_version, _ = validate_npm_package_version_query_params()
    # TODO: fetch all package versions

    package_report = get_most_recently_scored_package_report_or_raise(
        package_name, package_version, scored_after
    )
    return package_report.json_with_parents()


@api.route("/vulnerabilities", methods=["GET"])
def get_vulnerabilities_by_name_and_version() -> Dict:
    package_name, package_version, _ = validate_npm_package_version_query_params()
    return models.get_vulnerabilities_report(package_name, package_version)


@api.route("/graphs/<int:graph_id>", methods=["GET"])
def get_graph(graph_id):
    """
    Returns an svg rendered graphviz dot graph of the given scan

    graph result for the given graph_id
    """
    # TODO: check Accept header for a graphviz dot or image mimetype
    dot_graph: str = models.get_labelled_graphviz_graph(graph_id)
    print(dot_graph)  # TODO: debug log
    return graphviz.Source(dot_graph).pipe(format="svg").decode("utf-8")


@api.after_request
def add_standard_headers_to_static_routes(response):
    response.headers.update(STANDARD_HEADERS)
    return response


@api.route("/")
def index_page():
    return send_from_directory("static/", "index.html")
