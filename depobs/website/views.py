from datetime import datetime
import logging
from typing import Dict, Optional

from flask import abort, Blueprint, Response, request, send_from_directory
import graphviz
from werkzeug.exceptions import BadRequest, NotFound

from depobs.database import models
from depobs.website.scans import (
    validate_npm_package_version_query_params,
    validate_scored_after_ts_query_param,
)
from depobs.website.celery_tasks import get_celery_tasks

log = logging.getLogger(__name__)

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
            msg += f" scored after {self.scored_after}"
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

    npm_registry_entry: Optional[
        Dict
    ] = get_celery_tasks().fetch_package_entry_from_registry(
        package_name, package_version
    )
    if npm_registry_entry is None:
        return (
            dict(
                description=f"{e.description} Unable to find package {package_name} on the npm registry."
            ),
            404,
        )

    package_versions_on_registry: Dict = npm_registry_entry.get("versions", {})

    # if a scan of a specific package version was requested check that it exists
    if package_version is not None:
        package_version_exists = package_versions_on_registry.get(
            package_version, False
        )
        log.info(
            f"package: {package_name}@{package_version!r} on npm registry? {package_version_exists}"
        )
        return (
            dict(
                description=f"{e.description} Unable to find version "
                f"{package_version} of package {package_name} on the npm registry."
            ),
            404,
        )

    # start a task to scan the package
    result: celery.result.AsyncResult = get_celery_tasks().scan_npm_package_then_build_report_tree.delay(
        package_name, package_version
    )

    # TODO: make sure concurrent API calls don't introduce a data race
    if package_version is not None:
        package_report = models.insert_package_report_placeholder_or_update_task_id(
            package_name, package_version, result.id
        )
    else:
        # a version wasn't specified, so scan_npm_package will scan all versions
        # update or insert placeholders for all the versions referencing the same scan task
        package_reports = [
            models.insert_package_report_placeholder_or_update_task_id(
                package_name, reg_package_version, result.id
            )
            for reg_package_version in sorted(package_versions_on_registry.keys())
        ]
        log.info(
            f"inserted placeholder PackageReports for {package_name} at versions {[(pr.id, pr.version) for pr in package_reports]}"
        )

        if not len(package_reports):
            return (
                dict(
                    description=f"{e.description} Unable to find any versions "
                    f"of package {package_name} on the npm registry."
                ),
                404,
            )
        # return the report for the alphabetically highest version number (likely most recently published package)
        package_report = package_reports[-1]

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


@api.route("/statistics", methods=["GET"])
def get_statistics() -> Dict:
    return models.get_statistics()


@api.after_request
def add_standard_headers_to_static_routes(response):
    response.headers.update(STANDARD_HEADERS)
    return response


@api.route("/")
def index_page():
    return send_from_directory("static/", "index.html")
