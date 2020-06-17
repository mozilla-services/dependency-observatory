from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple, Type

from flask import (
    Blueprint,
    render_template,
    request,
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


def get_most_recently_scored_package_report_or_raise(
    package_name: str, package_version: str, scored_after: datetime
) -> models.PackageReport:
    "Returns a PackageReport or raises werkzeug 404 NotFound exception"
    package_report = models.get_most_recently_scored_package_report(
        package_name, package_version, scored_after
    )
    if package_report is None:
        raise NotFound(
            description=f"PackageReport {package_name}@{package_version} scored after {scored_after} not found."
        )
    return package_report


@api.after_request
def add_standard_headers_to_static_routes(response):
    response.headers.update(STANDARD_HEADERS)
    return response


@api.errorhandler(BadRequest)
def handle_bad_request(e):
    return dict(description=e.description), 400


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


@api.route("/statistics", methods=["GET"])
def get_statistics() -> Dict:
    return models.get_statistics()


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
