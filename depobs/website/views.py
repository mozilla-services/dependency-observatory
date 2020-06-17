from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple, Type

from flask import (
    Blueprint,
    jsonify,
    redirect,
    request,
    url_for,
    render_template,
)
import graphviz
import networkx as nx
from werkzeug.exceptions import BadRequest, NotFound

from depobs.database import models
from depobs.util import graph_traversal
from depobs.util import graph_util
from depobs.website.celery_tasks import get_celery_tasks
from depobs.worker import scoring
from depobs.worker import validators


log = logging.getLogger(__name__)

STANDARD_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Content-Security-Policy": (
        "default-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "font-src 'self'; "
        "img-src 'self'; "
        "style-src 'self'; "
        "script-src 'self'; "
        "connect-src 'self'; "
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
}

views_blueprint = api = Blueprint(
    "views_blueprint", __name__, template_folder="templates"
)


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
    if npm_registry_entries and len(npm_registry_entries) > 0:
        log.info(f"package registry entry for {package_name} found on npm")
        return True
    log.info(f"package registry entry for {package_name} not found")
    return False


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
    if npm_registry_entries and len(npm_registry_entries) > 0:
        npm_registry_entry = npm_registry_entries[0]
        assert isinstance(npm_registry_entry, dict) and "versions" in npm_registry_entry
        if npm_registry_entry and npm_registry_entry["versions"].get(
            package_version, None
        ):
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
            log.error(f"previous scan failed for pkg {package_name}@{package_version}")
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


@api.route("/api/package", methods=["GET"])
def show_package_by_name_and_version_if_available() -> Dict:
    scored_after = validate_scored_after_ts_query_param()
    package_name, package_version, _ = validate_npm_package_version_query_params()
    # TODO: fetch all package versions

    package_report = get_most_recently_scored_package_report_or_raise(
        package_name, package_version, scored_after
    )
    return package_report.json_with_dependencies()


@api.route("/api/parents", methods=["GET"])
def get_parents_by_name_and_version() -> Dict:
    scored_after = validate_scored_after_ts_query_param()
    package_name, package_version, _ = validate_npm_package_version_query_params()
    # TODO: fetch all package versions

    package_report = get_most_recently_scored_package_report_or_raise(
        package_name, package_version, scored_after
    )
    return package_report.json_with_parents()


@api.route("/package_report", methods=["GET"])
def show_package_report() -> Any:
    scored_after = validate_scored_after_ts_query_param()
    package_name, package_version, _ = validate_npm_package_version_query_params()

    package_report = get_most_recently_scored_package_report_or_raise(
        package_name, package_version, scored_after
    )
    return render_template(
        "package_report.html",
        package_report=package_report,
        get_direct_vulns=models.get_vulnerabilities_report,
    )


@api.route("/api/vulnerabilities", methods=["GET"])
def get_vulnerabilities_by_name_and_version() -> Dict:
    package_name, package_version, _ = validate_npm_package_version_query_params()
    return models.get_vulnerabilities_report(package_name, package_version)


@api.route("/statistics", methods=["GET"])
def get_statistics() -> Dict:
    return models.get_statistics()


@api.after_request
def add_standard_headers_to_static_routes(response):
    response.headers.update(STANDARD_HEADERS)
    return response


@api.route("/faq")
def faq_page() -> Any:
    return render_template("faq.html")


@api.route("/")
def index_page() -> Any:
    return render_template("search_index.html")


def validate_scored_after_ts_query_param() -> datetime:
    param_values = request.args.getlist("scored_after_ts", int)
    if len(param_values) > 1:
        raise BadRequest(description="only one scored_after_ts param supported")
    param_value = param_values[0] if len(param_values) else None
    # utcfromtimestamp might raise https://docs.python.org/3/library/exceptions.html#OverflowError
    return (
        datetime.utcfromtimestamp(param_value)
        if param_value
        else (datetime.now() - timedelta(days=(365 * 10)))
    )


def validate_npm_package_version_query_params() -> Tuple[str, str, str]:
    package_names = request.args.getlist("package_name", str)
    package_versions = request.args.getlist("package_version", str)
    package_managers = request.args.getlist("package_manager", str)
    if len(package_names) != 1:
        raise BadRequest(description="Exactly one package name required")
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

    package_name_validation_error = validators.get_npm_package_name_validation_error(
        package_name
    )
    if package_name_validation_error is not None:
        raise BadRequest(description=str(package_name_validation_error))

    if package_version:
        package_version_validation_error = validators.get_npm_package_version_validation_error(
            package_version
        )
        if package_version_validation_error is not None:
            raise BadRequest(description=str(package_version_validation_error))

    if package_manager != "npm":
        raise BadRequest(description="only the package manager 'npm' supported")

    return package_name, package_version, package_manager


@api.route("/api/scan", methods=["POST"])
def scan():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    result: celery.result.AsyncResult = get_celery_tasks().scan_npm_package.delay(
        package_name, package_version
    )
    return dict(task_id=result.id)


@api.route("/api/build_report_tree", methods=["POST"])
def build_report_tree():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    result: celery.result.AsyncResult = get_celery_tasks().build_report_tree.delay(
        (package_name, package_version)
    )
    return dict(task_id=result.id)


@api.route("/api/scan_then_build_report_tree", methods=["POST"])
def scan_npm_package_then_build_report_tree():
    package_name, package_version, _ = validate_npm_package_version_query_params()
    result: celery.result.AsyncResult = get_celery_tasks().scan_npm_package_then_build_report_tree.delay(
        package_name, package_version
    )
    return dict(task_id=result.id)


@api.route("/score_details/graphs/<int:graph_id>", methods=["GET"])
def get_graph(graph_id):
    """
    Returns an svg rendered graphviz dot graph of the given scan

    graph result for the given graph_id
    """
    db_graph: models.PackageGraph = models.get_graph_by_id(graph_id)
    g: nx.DiGraph = graph_util.package_graph_to_networkx_graph(db_graph)
    graph_util.update_node_attrs(
        g,
        label={
            pv.id: f"{pv.name}@{pv.version}"
            for pv in db_graph.distinct_package_versions_by_id.values()
        },
    )
    dot_graph: graphviz.Digraph = graph_util.nx_digraph_to_graphviz_digraph(g)
    dot_graph.attr(rankdir="LR")

    log.debug(f"dot for graph {graph_id}: {dot_graph!r}")
    return dot_graph.pipe(format="svg").decode("utf-8")


@api.route("/score_details/condensate_graphs/<int:graph_id>", methods=["GET"])
def get_condensate_graph(graph_id):
    """
    Returns an svg rendered graphviz dot graph of the given scan

    graph result for the given graph_id
    """
    db_graph: models.PackageGraph = models.get_graph_by_id(graph_id)
    g: nx.DiGraph = graph_util.package_graph_to_networkx_graph(db_graph)
    c: nx.DiGraph = graph_traversal.condensation(g)

    graph_util.update_node_attrs(
        g,
        label={
            pv.id: f"{pv.name}@{pv.version}"
            for pv in db_graph.distinct_package_versions_by_id.values()
        },
    )
    dot_graph: graphviz.Digraph = graph_util.nx_digraph_to_graphviz_digraph(c)
    dot_graph.attr(rankdir="LR")

    for scc_node_ids in graph_traversal.outer_in_dag_iter(c):
        with dot_graph.subgraph() as s:
            s.attr(rank="same")
            for scc_node_id in scc_node_ids:
                log.debug(
                    f"scc_node_id {scc_node_id} members {c.nodes[scc_node_id]['members']}"
                )
                component_pkgs = "\n".join(
                    g.nodes[m_id]["label"] for m_id in c.nodes[scc_node_id]["members"]
                )
                s.node(
                    str(scc_node_id),
                    label=f"scc_id: {scc_node_id}\nmembers: {component_pkgs}",
                )

    log.debug(f"dot for condensate graph {graph_id}: {dot_graph!r}")
    return dot_graph.pipe(format="svg").decode("utf-8")


@api.route(
    "/score_details/score_component_graph/<int:graph_id>/<string:package_report_field>",
    methods=["GET"],
)
def get_scoring_graph(graph_id: int, package_report_field: str):
    log.info(
        f"getting scoring graph {graph_id} for package report field {package_report_field}"
    )
    component: Optional[
        Type[scoring.ScoreComponent]
    ] = scoring.find_component_with_package_report_field(package_report_field)
    if component is None:
        return NotFound(
            f"Unable to find scoring component to provide field {package_report_field}"
        )
    log.info(f"rendering score component graph with component: {component}")

    # find graph and score it with that component
    db_graph: models.PackageGraph = models.get_graph_by_id(graph_id)
    g: nx.DiGraph = graph_util.package_graph_to_networkx_graph(db_graph)

    reports_by_package_version_id: Dict[
        models.PackageVersionID, models.PackageReport
    ] = scoring.score_package_graph(db_graph, [component], g)

    graph_util.update_node_attrs(
        g,
        report=reports_by_package_version_id,
        label={
            pv.id: f"{pv.name}@{pv.version}"
            for pv in db_graph.distinct_package_versions_by_id.values()
        },
    )

    dot_graph: graphviz.Digraph = graph_util.nx_digraph_to_graphviz_digraph(g)
    dot_graph.attr(rankdir="LR")

    for node_id, node_data in g.nodes(data=True):
        # add package report field name and value to the label
        label = f"{node_data['label']}\n\n{package_report_field}:\n{getattr(node_data['report'], package_report_field, None)}"
        dot_graph.node(str(node_id), label=label)

    log.debug(f"rendering score component graph: {dot_graph!r}")
    return dot_graph.pipe(format="svg").decode("utf-8")
