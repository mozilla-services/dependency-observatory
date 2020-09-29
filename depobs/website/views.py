from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple, Type
from collections import OrderedDict

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
import altair as alt
import graphviz
from marshmallow import ValidationError
import networkx as nx
from werkzeug.exceptions import BadRequest, NotFound

from depobs.website.schemas import (
    JSONResultSchema,
    PackageReportParamsSchema,
    ScanSchema,
    ScanScoreNPMDepFilesRequestParamsSchema,
    ScanScoreNPMPackageRequestParamsSchema,
)
from depobs.database import models
from depobs.util import graph_traversal
from depobs.util import graph_util
from depobs.util.datavis_util import (
    package_score_reports_to_scores_histogram,
    package_score_reports_to_score_grades_histogram,
)
from depobs.worker import scoring


log = logging.getLogger(__name__)

STANDARD_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    # NB: altair/vega uses style-src unsafe-inline
    "Content-Security-Policy": (
        "default-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "font-src 'self'; "
        "img-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
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
    package_name: str, package_version: str, scored_after: Optional[datetime] = None
) -> models.PackageReport:
    "Returns a PackageReport or raises werkzeug 404 NotFound exception"
    if scored_after is None:
        scored_after = datetime.now() - timedelta(
            days=current_app.config["DEFAULT_SCORED_AFTER_DAYS"]
        )

    package_report = models.get_most_recently_scored_package_report_query(
        package_name, package_version, scored_after
    ).one_or_none()
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
    """Returns a report for the provided package, name, version, and manager.

    When version is 'latest' redirects to the most recently scored
    report for that package_name.
    """
    try:
        report = PackageReportParamsSchema().load(data=request.args)
    except ValidationError as err:
        return err.messages, 422

    package_report = get_most_recently_scored_package_report_or_raise(
        report.package_name,
        report.package_version if report.package_version != "latest" else None,
    )
    if report.package_version == "latest":
        return redirect(
            url_for(
                ".show_package_report",
                package_name=report.package_name,
                package_version=package_report.version,
                package_manager=report.package_manager,
            )
        )
    package_version = models.get_package_version_id_query(
        models.PackageVersion(
            name=package_report.package, version=package_report.version
        )
    ).one_or_none()
    return render_template(
        "package_report.html",
        package_report=package_report,
        package_report_fields=scoring.all_score_component_fields,
        direct_vulnerabilities=models.get_advisories_by_package_version_ids_query(
            package_version
        )
        if package_version
        else [],
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
        package_name=report.package_name,
        npmsio_score=models.get_npmsio_score_query(report.package_name).one_or_none(),
        registry_entries=list(
            models.get_NPMRegistryEntry(report.package_name, None)
            .order_by(models.NPMRegistryEntry.published_at.desc())
            .all()
        ),
    )


@api.route("/graphs/<int:graph_id>/score_code_histogram", methods=["GET", "HEAD"])
def get_graph_score_code_histogram_spec(graph_id: int):
    """
    Returns a vega spec for a histogram of the graph score codes/grades
    """
    db_graph: models.PackageGraph = models.get_graph_by_id(graph_id)
    return (
        package_score_reports_to_score_grades_histogram(
            db_graph.distinct_package_reports
        )
        .properties(width=400, height=400)
        .configure_axis(grid=False)
        .to_json()
    )


@api.route("/graphs/<int:graph_id>/score_histogram", methods=["GET", "HEAD"])
def get_graph_score_histogram_spec(graph_id: int):
    """
    Returns a vega spec for a histogram of the graph scores
    """
    db_graph: models.PackageGraph = models.get_graph_by_id(graph_id)
    return (
        package_score_reports_to_scores_histogram(db_graph.distinct_package_reports)
        .properties(width=400, height=400)
        .configure_axis(grid=False)
        .to_json()
    )


@api.route("/dep_files_reports/<int:scan_id>", methods=["GET", "HEAD"])
def show_dep_files_report(scan_id: int) -> Any:
    """
    Renders the dep files report for the provided scan ID
    (alternatively could index on and use hashes of the dep files as
    query params).
    """
    scan = models.get_scan_by_id(scan_id).one()
    return render_template(
        "dep_files_report.html",
        name=f"scan {scan_id}",
        scan=scan,
        package_report_fields=scoring.all_score_component_fields,
        advisories=models.get_advisories_by_package_version_ids_query(
            scan.package_graph.distinct_package_ids
        ).all(),
    )


@api.route("/statistics/histogram.vg.json")
def get_histogram() -> Any:
    """
    Returns a vega spec and data to render a histogram of the
    distribution of score codes for all reports
    """
    scores = models.get_statistics()
    counts = scores["score_codes_histogram"]

    # Required to pass typing CI test
    assert isinstance(counts, dict)

    data = alt.Data(
        values=[
            dict(score_code=score_code, count=counts.get(score_code, 0))
            for score_code in ["A", "B", "C", "D", "E"]
        ]
    )
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("score_code:O", axis=alt.Axis(title="package grade")),
            y=alt.Y("count:Q", axis=alt.Axis(title="count")),
        )
        .configure_axis(grid=False)
        .properties(width=600, height=400)
        .to_json()
    )


@api.route("/statistics/distribution.vg.json")
def get_distribution() -> Any:
    scores = models.get_statistics_scores()

    data = alt.Data(values=[dict(score=score) for score in scores])
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("score:O", bin=True, axis=alt.Axis(title="package score")),
            y=alt.Y("count()", axis=alt.Axis(title="count")),
        )
        .configure_axis(grid=False)
        .properties(width=600, height=400)
        .to_json()
    )


@api.route("/statistics", methods=["GET"])
def get_statistics() -> Any:
    scores = models.get_statistics()["score_codes_histogram"]

    # Required to pass typing CI test
    assert isinstance(scores, dict)

    # Sort the dictionary alphabetically by key
    sorted_scores = OrderedDict()
    for key, value in sorted(scores.items()):
        sorted_scores[key] = value

    return render_template("statistics.html", sorted_scores=sorted_scores)


@api.route("/faq")
def faq_page() -> Any:
    return render_template("faq.html")


@api.route("/")
def index_page() -> Any:
    return render_template(
        "search_index.html",
        scored_after_days=current_app.config["DEFAULT_SCORED_AFTER_DAYS"],
    )


def schema_to_dep_files_scan(scan_config) -> models.Scan:
    dep_files: List[models.ScanFileURL] = [
        {
            "filename": "package.json",
            "url": scan_config.manifest_url,
        }
    ]
    if scan_config.lockfile_url:
        dep_files.append(
            {
                "filename": "package-lock.json",
                "url": scan_config.lockfile_url,
            }
        )
    if scan_config.shrinkwrap_url:
        dep_files.append(
            {
                "filename": "npm-shrinkwrap.json",
                "url": scan_config.shrinkwrap_url,
            }
        )
    return models.dependency_files_to_scan(dep_files)


def schema_to_package_scan(scan_config) -> models.Scan:
    if scan_config.package_versions_type == "specific-version":
        version = scan_config.package_version
    elif scan_config.package_versions_type == "releases":
        version = None
    elif scan_config.package_versions_type == "latest":
        version = "latest"
    else:
        raise NotImplementedError()

    return models.package_name_and_version_to_scan(
        scan_config.package_name,
        version,
    )


@api.route("/api/v1/scans", methods=["POST"])
def queue_scan() -> Tuple[Dict, int]:
    """
    Queues a scan for package version or versions and returns the scan
    JSON with status 202
    """
    body = request.get_json()
    log.warning(f"received scan JSON body: {body}")
    if (
        isinstance(body, dict)
        and "scan_type" in body
        and body["scan_type"] == "scan_score_npm_dep_files"
    ):
        schema = ScanScoreNPMDepFilesRequestParamsSchema
        loader = schema_to_dep_files_scan
    else:
        schema = ScanScoreNPMPackageRequestParamsSchema
        loader = schema_to_package_scan

    try:
        scan_config = schema().load(data=body)
    except ValidationError as err:
        return err.messages, 422

    log.info(f"deserialized scan JSON to {scan_config.scan_type}: {scan_config}")  # type: ignore
    if scan_config.scan_type not in current_app.config["WEB_JOB_NAMES"]:  # type: ignore
        raise BadRequest(description="scan type not allowed or does not exist for app")

    scan = models.save_scan_with_status(
        loader(scan_config),
        "queued",
    )
    log.info(f"queued scan {scan.id}")
    return ScanSchema().dump(scan), 202


@api.route("/api/v1/scans/<int:scan_id>", methods=["GET"])
def get_scan(scan_id: int) -> Dict:
    """
    Returns the scan as JSON
    """
    log.info(f"fetching scan {scan_id}")
    return ScanSchema().dump(models.get_scan_by_id(scan_id).one())


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
    scan = models.get_scan_by_id(scan_id).one_or_none()
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


@api.route("/recent_package_reports", methods=["GET", "HEAD"])
def show_recent_package_reports() -> Any:
    """Returns the ten most recent package and dep files scans."""
    return render_template(
        "recent_package_reports.html",
        reports=models.get_recent_package_reports_query(),
    )
