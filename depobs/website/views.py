from datetime import datetime, timedelta
import logging
from random import randrange
import time
from typing import Any, Dict, List, Optional, Tuple, Type
from io import BytesIO, StringIO

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    render_template,
    request,
    url_for,
    Response,
)
import graphviz
from marshmallow import ValidationError
import networkx as nx
import urllib3
from werkzeug.exceptions import BadGateway, BadRequest, NotFound, NotImplemented
import seaborn as sb

from depobs.website.schemas import (
    JobParamsSchema,
    JSONResultSchema,
    PackageReportParamsSchema,
    ScanSchema,
)
from depobs.database import models
from depobs.util import graph_traversal
from depobs.util import graph_util
from depobs.worker import k8s
from depobs.worker import tasks
from depobs.worker import scoring


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


def stream_template(template_name, **context):
    current_app.update_template_context(context)
    t = current_app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv


def get_most_recently_scored_package_report_or_raise(
    package_name: str, package_version: str, scored_after: Optional[datetime] = None
) -> models.PackageReport:
    "Returns a PackageReport or raises werkzeug 404 NotFound exception"
    if scored_after is None:
        scored_after = datetime.now() - timedelta(
            days=current_app.config["DEFAULT_SCORED_AFTER_DAYS"]
        )

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
    response.headers["X-REQUEST-ID"] = g.get("_request_id", None)
    return response


@api.errorhandler(BadRequest)
def handle_bad_request(e):
    return dict(description=e.description), 400


@api.route("/package_report", methods=["GET", "HEAD"])
def show_package_report() -> Any:
    try:
        report = PackageReportParamsSchema().load(data=request.args)
    except ValidationError as err:
        return err.messages, 422

    package_report = get_most_recently_scored_package_report_or_raise(
        report.package_name, report.package_version
    )
    return render_template(
        "package_report.html",
        package_report=package_report,
        package_report_fields=scoring.all_score_component_fields,
        get_direct_vulns=models.get_vulnerabilities_report,
    )


@api.route("/package_changelog", methods=["GET", "HEAD"])
def show_package_changelog() -> Any:
    try:
        report = PackageReportParamsSchema().load(data=request.args)
    except ValidationError as err:
        return err.messages, 422

    package_reports = get_most_recently_scored_package_report_or_raise(
        report.package_name, report.package_version
    )
    return render_template(
        "package_changelog.html",
        name=report.package_name,
        versions=list(
            models.get_npm_registry_entries_to_scan(report.package_name, None).all()
        ),
    )


@api.route("/histogram.png")
def get_histogram() -> Any:

    scores = models.get_statistics()
    counts = scores["score_codes_histogram"]

    # Required to pass typing CI test
    assert isinstance(counts, dict)

    # This is a workaround to get the data into a format that seaborn will accept
    letters = list()
    for letter in counts:
        for i in range(counts[letter]):
            letters.append(letter)

    data = {"score_code": letters}

    img = BytesIO()
    fig = sb.countplot(
        x="score_code", data=data, order=["A", "B", "C", "D", "E"],
    ).get_figure()
    fig.savefig(img, format="png")
    fig.clf()
    return Response(img.getvalue(), mimetype="image/png")


@api.route("/distribution.png")
def get_distribution() -> Any:

    scores = models.get_statistics_scores()

    img = BytesIO()
    fig = sb.distplot(
        scores, bins=15, kde=False, norm_hist=False, axlabel="package score"
    ).get_figure()
    fig.savefig(img, format="png")
    fig.clf()
    return Response(img.getvalue(), mimetype="image/png")


@api.route("/statistics", methods=["GET"])
def get_statistics() -> Any:
    return render_template("statistics.html")


@api.route("/faq")
def faq_page() -> Any:
    return render_template("faq.html")


@api.route("/")
def index_page() -> Any:
    return render_template(
        "search_index.html",
        scored_after_days=current_app.config["DEFAULT_SCORED_AFTER_DAYS"],
    )


@api.route("/api/v1/scans", methods=["POST"])
def queue_scan() -> Tuple[Dict, int]:
    """
    Queues a scan for a package and returns the scan JSON with status 202
    """
    job_body = request.get_json()
    log.debug(f"received job JSON body: {job_body}")
    try:
        web_job_config = JobParamsSchema().load(data=job_body)
    except ValidationError as err:
        return err.messages, 422

    log.info(f"deserialized job JSON to {web_job_config.name}: {web_job_config}")
    if web_job_config.name not in current_app.config["WEB_JOB_NAMES"]:
        raise BadRequest(description="job not allowed or does not exist for app")

    scan = models.Scan(params=JobParamsSchema().dump(web_job_config), status="queued",)
    models.db.session.add(scan)
    models.db.session.commit()
    log.info(f"queued job {scan.id}")

    return ScanSchema().dump(scan), 202


@api.route("/api/v1/scans/<int:scan_id>", methods=["GET"])
def get_scan(scan_id: int) -> Dict:
    """
    Returns the scan as JSON
    """
    log.info(f"fetching scan {scan_id}")
    return ScanSchema().dump(
        models.db.session.query(models.Scan).filter_by(id=scan_id).one()
    )


@api.route("/api/v1/scans/<int:scan_id>/logs", methods=["GET"])
def read_scan_logs(scan_id: int) -> Dict:
    """
    Returns the scan JSONResults
    """
    json_results = list(models.get_scan_results_by_id(scan_id).all())
    if not json_results:
        raise NotFound

    serialized = [JSONResultSchema().dump(json_result) for json_result in json_results]
    return jsonify(serialized)


@api.route("/scans/<int:scan_id>/logs", methods=["GET"])
def render_scan_logs(scan_id: int):
    """Renders the scan status and job JSONResults

    When refresh is True (the default) the scan page will refresh and
    redirect to the package report page if the scan completes
    successfully.
    """
    refresh = request.args.get("refresh", False, bool)
    log.info(f"rendering job logs for scan {scan_id} with refresh {refresh}")
    scan = models.db.session.query(models.Scan).filter_by(id=scan_id).one_or_none()
    json_results = []
    if scan is not None:
        json_results = list(models.get_scan_results_by_id_on_job_name(scan_id).all())

    return render_template(
        "scan_job_logs.html", scan=scan, results=json_results, refresh=refresh
    )


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
    "/score_details/score_component_graphs/<int:graph_id>/<string:package_report_field>",
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
