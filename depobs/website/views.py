from datetime import datetime
import logging
from typing import Dict, List, Optional

from flask import (
    abort,
    Blueprint,
    Response,
    redirect,
    request,
    send_from_directory,
    url_for,
)
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

    @staticmethod
    def format_description(
        package_name: str,
        package_version: Optional[str] = None,
        scored_after: Optional[datetime] = None,
    ):
        msg = f"PackageReport {package_name}"
        if package_version is not None:
            msg += f"@{package_version}"
        if scored_after is not None:
            msg += f" scored after {scored_after}"
        return msg + " not found."


def get_most_recently_scored_package_report_or_raise(
    package_name: str, package_version: str, scored_after: datetime
) -> models.PackageReport:
    "Returns a PackageReport or raises a PackageReportNotFound exception"
    package_report = models.get_most_recently_scored_package_report(
        package_name, package_version, scored_after
    )
    if package_report is None:
        not_found = PackageReportNotFound(
            package_name=package_name,
            package_version=package_version,
            scored_after=scored_after,
        )
        not_found.description = PackageReportNotFound.format_description(
            package_name=package_name,
            package_version=package_version,
            scored_after=scored_after,
        )
        raise not_found

    return package_report


def check_package_name_registered(package_name: str) -> bool:
    """
    Returns a bool representing whether the package name was found on
    the npm registry or in the debobs DB.

    Hits the npm registry and saves registry entries for each version
    found when the package name isn't found in the debobs DB
    """
    # try npm_registry_entries in our db first since npm registry entries can be big and slow to fetch
    if models.get_package_name_in_npm_registry_data(package_name):
        log.info(f"package registry entry for {package_name} found in depobs db")
        return True

    npm_registry_entries: List[
        Optional[Dict]
    ] = get_celery_tasks().fetch_and_save_registry_entries([package_name])
    if (
        npm_registry_entries is None
        or len(npm_registry_entries) < 1
        or npm_registry_entries[0] is not None
    ):
        log.info(f"package registry entry for {package_name} not found")
        return False
    log.info(f"package registry entry for {package_name} found on npm")
    return True


def check_package_version_registered(package_name: str, package_version: str) -> bool:
    """
    Returns bool representing whether the package version was found
    on the npm registry or in the debobs DB.

    Hits the npm registry and saves registry entries for each version
    found when the package version isn't found in the debobs DB.
    """
    if models.get_npm_registry_data(package_name, package_version).one_or_none():
        log.info(
            f"package registry entry for {package_name}@{package_version} found in depobs db"
        )
        return True

    # TODO: don't call if we already hit it for the name check
    # TODO: if the NPM API supports it, only fetch changes from our registry entry version
    npm_registry_entries: List[
        Optional[Dict]
    ] = get_celery_tasks().fetch_and_save_registry_entries([package_name])
    if (
        npm_registry_entries is None
        or len(npm_registry_entries) < 1
        or npm_registry_entries[0] is not None
    ):
        log.info(f"failed to find new versions in registry for {package_name}")
        return False

    npm_registry_entry = npm_registry_entries[0]
    if npm_registry_entry and npm_registry_entry.get("versions", package_version, None):
        log.info(
            f"package registry entry for {package_name}@{package_version} found on npm"
        )
        return True

    log.info(
        f"package registry entry for {package_name}@{package_version} not found on npm"
    )
    return False


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
            return package_report.report_json, 502
        return package_report.report_json, 202

    if not check_package_name_registered(package_name):
        return (
            dict(
                description=f"Unable to find package named {package_name!r} on the npm registry."
            ),
            404,
        )
    if package_version and not check_package_version_registered(
        package_name, package_version
    ):
        log.info(
            f"package version: {package_name}@{package_version!r} not found in depobs db"
        )
        return (
            dict(
                description=f"Unable to find version "
                f"{package_version!r} of package {package_name!r} on the npm registry."
            ),
            404,
        )
    # save any registry entries we fetch checking for package name and version
    models.db.session.commit()

    # start a task to scan the package
    scan_task: celery.result.AsyncResult = get_celery_tasks().scan_npm_package_then_build_report_tree.delay(
        package_name, package_version
    )

    # TODO: make sure concurrent API calls don't introduce a data race
    if package_version is not None:
        package_report = models.insert_package_report_placeholder_or_update_task_id(
            package_name, package_version, scan_task.id
        )
    else:
        # a version wasn't specified, so scan_npm_package will scan all versions
        # update or insert placeholders for all the versions referencing the same scan task
        package_reports = [
            models.insert_package_report_placeholder_or_update_task_id(
                package_name, entry.package_version, scan_task.id
            )
            for entry in models.get_NPMRegistryEntry(package_name)
        ]
        log.info(
            f"inserted placeholder PackageReports for {package_name} at versions {[(pr.id, pr.version) for pr in package_reports]}"
        )

        if not len(package_reports):
            return (
                dict(
                    description=f"Unable to find any versions "
                    f"of package {package_name!r} on the npm registry."
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
    return redirect(url_for("score_details_blueprint.get_graph", graph_id=graph_id))


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
