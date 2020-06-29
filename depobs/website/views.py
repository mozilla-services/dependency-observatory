from datetime import datetime, timedelta
import logging
from random import randrange
import time
from typing import Any, Dict, List, Optional, Tuple, Type

from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    render_template,
    request,
    stream_with_context,
    url_for,
)
import graphviz
from marshmallow import ValidationError
import networkx as nx
import urllib3
from werkzeug.exceptions import BadGateway, BadRequest, NotFound

from depobs.website.schemas import JobParamsSchema, PackageReportParamsSchema
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
    return render_template(
        "search_index.html",
        scored_after_days=current_app.config["DEFAULT_SCORED_AFTER_DAYS"],
    )


@api.route("/api/v1/jobs", methods=["POST"])
def create_job():
    """
    Creates a k8s job for a package and returns the k8s job object
    """
    job_body = request.get_json()
    log.debug(f"received job JSON body: {job_body}")
    try:
        web_job_config = JobParamsSchema().load(data=job_body)
    except ValidationError as err:
        return err.messages, 422

    app_job_config = current_app.config["WEB_JOB_CONFIGS"].get(
        web_job_config.name, None
    )
    log.info(f"deserialized job JSON to {web_job_config.name}: {web_job_config}")
    if app_job_config is None:
        raise BadRequest(description="job not allowed or does not exist for app")

    # NB: name must be shorter than 64 chars
    k8s_job_config: k8s.KubeJobConfig = dict(
        **app_job_config,
        name=f"{web_job_config.name.lower().replace('_', '-')}-{hex(randrange(1 << 32))[2:]}",
        args=app_job_config["base_args"] + web_job_config.args,
    )
    client = k8s.get_client()
    log.info(f"creating k8s job {k8s_job_config} with k8s job config: {k8s_job_config}")
    return k8s.create_job(k8s_job_config).to_dict()


@api.route("/api/v1/jobs/<string:job_name>", methods=["GET"])
def get_job(job_name: str):
    """
    Returns the k8s job object (including status) in the default app namespace
    """
    log.info(f"fetching k8s job {job_name}")
    job = k8s.read_job(
        namespace=current_app.config["DEFAULT_JOB_NAMESPACE"], name=job_name
    )
    return job.to_dict()


@api.route("/api/v1/jobs/<string:job_name>", methods=["DELETE"])
def delete_job(job_name: str):
    """
    Returns the k8s job object (including status) for the default app namespace
    """
    log.info(f"deleting k8s job {job_name}")
    return k8s.delete_job(
        namespace=current_app.config["DEFAULT_JOB_NAMESPACE"], name=job_name
    ).to_dict()


@api.route("/api/v1/jobs/<string:job_name>/logs", methods=["GET"])
def read_job_logs(job_name: str):
    return k8s.read_job_logs(
        namespace=current_app.config["DEFAULT_JOB_NAMESPACE"], name=job_name
    )


@api.route("/jobs/<string:job_name>/logs", methods=["GET"])
def render_job_logs(job_name: str):
    def generate():
        log.info(f"waiting for the job {job_name} container to start")
        yield dict(event_type="new_phase", message="finding job container")

        try:
            job_pod_name = k8s.get_pod_container_name(
                k8s.get_job_pod(
                    namespace=current_app.config["DEFAULT_JOB_NAMESPACE"], name=job_name
                )
            )
        except urllib3.exceptions.MaxRetryError as err:
            log.info(f"job pod not ready: {err}")
            job_pod_name = None

        log.info(f"job {job_name} got pod name {job_pod_name}")
        if job_pod_name is None:
            for event in k8s.watch_job_pods(
                namespace=current_app.config["DEFAULT_JOB_NAMESPACE"], name=job_name
            ):
                log.info(
                    f"job {job_name} pod {event['type']} status {event['object'].status.phase} container statuses {event['object'].status.container_statuses}"
                )
                yield dict(event_type="k8s_pod_event", k8s_event=event)
                if event["type"] == "ERROR":
                    log.error(f"error with job {job_name} pod {event}")
                    raise StopIteration

                assert event["type"] in {"ADDED", "MODIFIED"}
                job_pod_name = k8s.get_pod_container_name(event["object"])
                if job_pod_name is not None:
                    break

        log.info(f"streaming job {job_name} logs for pod {job_pod_name}")
        yield dict(event_type="new_phase", message=f"logs for pod {job_pod_name}")
        for i, line in enumerate(
            k8s.tail_job_logs(
                namespace=current_app.config["DEFAULT_JOB_NAMESPACE"], name=job_name,
            )
        ):
            if i % 10:
                log.debug(f"streaming job {job_name} logs line {i}")
            else:
                log.info(f"streaming job {job_name} logs line {i}")
            yield dict(event_type="k8s_container_log_line", log_line=line)

        log.info(f"waiting for job {job_name} completion")
        for event in k8s.watch_job(
            namespace=current_app.config["DEFAULT_JOB_NAMESPACE"], name=job_name
        ):
            log.info(f"job {job_name} {event['type']} status {event['object'].status}")
            job = event["object"]
            if job.status.succeeded:
                log.info(f"got finished job {job.status.succeeded} {job}")
                package_name, package_version = job.spec.template.spec.containers[
                    0
                ].args[3:]
                yield dict(
                    event_type="new_phase",
                    message=f"job succeeded! Redirecting to the package report at: ",
                    redirect_url=url_for(
                        "views_blueprint.show_package_report",
                        package_manager="npm",
                        package_name=package_name,
                        package_version=package_version,
                    ),
                )
                break
            elif job.status.failed:
                log.error(f"job {job_name} failed")
                yield dict(
                    event_type="new_phase", message=f"job failed",
                )
                break

        yield dict(
            event_type="new_phase", message=f"finished",
        )

    return Response(
        stream_with_context(
            stream_template("job_logs.html", job_name=job_name, events=generate())
        )
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
