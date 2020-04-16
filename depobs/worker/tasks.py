import argparse
import asyncio
import datetime
import os
import sys
from typing import AbstractSet, Callable, Dict, Generator, List, Optional, Tuple, Union
import logging

from celery.utils.log import get_task_logger
import celery.result
import networkx as nx
from networkx.algorithms.dag import descendants, is_directed_acyclic_graph

from depobs.website.do import create_celery_app
import depobs.website.models as models
from depobs.website.models import (
    NPMRegistryEntry,
    PackageReport,
    PackageLatestReport,
    get_package_report,
    get_npms_io_score,
    get_NPMRegistryEntry,
    get_maintainers_contributors,
    get_npm_registry_data,
    get_vulnerability_counts,
    store_package_report,
    store_package_reports,
    get_most_recently_inserted_package_from_name_and_version,
    get_latest_graph_including_package_as_parent,
    get_placeholder_entry,
    get_networkx_graph_and_nodes,
)
import depobs.worker.validators as validators

# import exc_to_str to resolve import cycle for the following depobs.scanner.clients
from depobs.scanner.pipelines.util import exc_to_str as _
from depobs.scanner.clients.npmsio import fetch_npmsio_scores
from depobs.scanner.clients.npm_registry import fetch_npm_registry_metadata
from depobs.scanner.db.schema import (
    PackageVersion,
    PackageGraph,
)

log = get_task_logger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

# http client config
# an npm registry access token for fetch_npm_registry_metadata. Defaults NPM_PAT env var. Should be read-only.
NPM_PAT = os.environ.get("NPM_PAT", None)

# celery will try to import these if they're public vars (no _ prefix)
_NPM_CLIENT_CONFIG = argparse.Namespace(
    user_agent="https://github.com/mozilla-services/dependency-observatory-scanner (foxsec+dependency+observatory@mozilla.com)",
    total_timeout=30,
    max_connections=1,
    max_retries=1,
    package_batch_size=1,
    dry_run=False,
    npm_auth_token=NPM_PAT,
)
_NPMSIO_CLIENT_CONFIG = argparse.Namespace(
    user_agent="https://github.com/mozilla-services/dependency-observatory-scanner (foxsec+dependency+observatory@mozilla.com)",
    total_timeout=10,
    max_connections=1,
    package_batch_size=1,
    dry_run=False,
)

app = create_celery_app()


@app.task()
def add(x, y):
    return x + y


@app.task()
def scan_npm_package(package_name: str, package_version: Optional[str] = None) -> None:
    package_name_validation_error = validators.get_npm_package_name_validation_error(
        package_name
    )
    if package_name_validation_error is not None:
        raise package_name_validation_error

    if package_version:
        package_version_validation_error = validators.get_npm_package_version_validation_error(
            package_version
        )
        if package_version_validation_error is not None:
            raise package_version_validation_error


    return (package_name, package_version)


@app.task()
def score_package(
    package_name: str,
    package_version: str,
    direct_dep_reports: List[PackageReport],
    all_deps_count: int = 0,
) -> PackageReport:
    log.info(
        f"scoring package: {package_name}@{package_version} with direct deps {list((r.package, r.version) for r in direct_dep_reports)}"
    )
    pr = PackageReport()
    pr.package = package_name
    pr.version = package_version

    plr = PackageLatestReport()
    plr.package = package_name
    plr.version = package_version

    pr.npmsio_score = get_npms_io_score(package_name, package_version).first()

    pr.directVulnsCritical_score = 0
    pr.directVulnsHigh_score = 0
    pr.directVulnsMedium_score = 0
    pr.directVulnsLow_score = 0

    # Direct vulnerability counts
    for package, version, severity, count in get_vulnerability_counts(
        package_name, package_version
    ):
        severity = severity.lower()
        log.info(
            f"scoring package: {package_name}@{package_version} found vulnerable dep: \t{package}\t{version}\t{severity}\t{count}"
        )
        if severity == "critical":
            pr.directVulnsCritical_score = count
        elif severity == "high":
            pr.directVulnsHigh_score = count
        elif severity in ("medium", "moderate"):
            pr.directVulnsMedium_score = count
        elif severity == "low":
            pr.directVulnsLow_score = count
        else:
            log.error(
                f"unexpected severity {severity} for package {package} / version {version}"
            )

    for published_at, maintainers, contributors in get_npm_registry_data(
        package_name, package_version
    ):
        pr.release_date = published_at
        if maintainers is not None:
            pr.authors = len(maintainers)
        else:
            pr.authors = 0
        if contributors is not None:
            pr.contributors = len(contributors)
        else:
            pr.contributors = 0

    pr.immediate_deps = len(direct_dep_reports)
    pr.all_deps = all_deps_count

    # Indirect counts
    pr.indirectVulnsCritical_score = 0
    pr.indirectVulnsHigh_score = 0
    pr.indirectVulnsMedium_score = 0
    pr.indirectVulnsLow_score = 0

    dep_rep_count = 0
    for report in direct_dep_reports:
        dep_rep_count += 1
        for severity in ("Critical", "High", "Medium", "Low"):
            setattr(
                pr,
                f"indirectVulns{severity}_score",
                getattr(report, f"directVulns{severity}_score", 0)
                + getattr(report, f"indirectVulns{severity}_score", 0),
            )
        pr.dependencies.append(report)

    if dep_rep_count != pr.immediate_deps:
        log.error(
            f"expected {pr.immediate_deps} dependencies but got {dep_rep_count} for package {package_name} / version {package_version}"
        )

    pr.scoring_date = datetime.datetime.now()
    pr.status = "scanned"
    return pr


def outer_in_iter(g: nx.DiGraph) -> Generator[List[int], None, None]:
    """
    For a DAG with unique node IDs with type int, iterates from outer
    / leafmost / least depended upon nodes to inner nodes yielding sets
    of node IDs.

    Yields each node ID once and visits them such that successive node ID sets
    only depend on/point to previously visited nodes.
    """
    if len(g.edges) == 0 or len(g.nodes) == 0:
        raise Exception("graph has no edges or nodes")
    if not is_directed_acyclic_graph(g):
        raise Exception("graph is not a DAG")

    visited: AbstractSet[int] = set()
    leaf_nodes = set([node for node in g.nodes() if g.out_degree(node) == 0])
    yield leaf_nodes
    visited.update(leaf_nodes)

    while True:
        points_to_visited = set(src for (src, _) in g.in_edges(visited))
        only_points_to_visited = set(
            node
            for node in points_to_visited
            if all(dst in visited for (_, dst) in g.out_edges(node))
        )
        new_only_points_to_visited = only_points_to_visited - visited
        if not bool(new_only_points_to_visited):  # visited nothing new
            assert len(visited) == len(g.nodes)
            break
        yield new_only_points_to_visited
        visited.update(only_points_to_visited)


def score_package_and_children(g: nx.DiGraph, package_versions: List[PackageVersion]):
    # refs: https://github.com/mozilla-services/dependency-observatory/issues/130#issuecomment-608017713
    package_versions_by_id: Dict[int, PackageVersion] = {
        pv.id: pv for pv in package_versions
    }
    # fill this up
    package_reports_by_id: Dict[int, PackageReport] = {}

    for package_version_ids in outer_in_iter(g):
        for package_version_id in package_version_ids:
            package = package_versions_by_id[package_version_id]
            package_reports_by_id[package_version_id] = score_package(
                package.name,
                package.version,
                direct_dep_reports=[
                    package_reports_by_id[direct_dep_package_version_id]
                    for direct_dep_package_version_id in g.successors(
                        package_version_id
                    )
                ],
                all_deps_count=len(descendants(g, package_version_id)),
            )

    return package_reports_by_id.values()


@app.task()
def build_report_tree(package_version_tuple: Tuple[str, str]) -> None:
    package_name, package_version = package_version_tuple

    package: Optional[
        PackageVersion
    ] = get_most_recently_inserted_package_from_name_and_version(
        package_name, package_version
    )
    if package is None:
        pr = get_placeholder_entry(package_name, package_version)
        if pr:
            pr.status = "error"
            store_package_report(pr)
        raise Exception(
            f"PackageVersion not found for {package_name} {package_version}."
        )

    graph: Optional[PackageGraph] = get_latest_graph_including_package_as_parent(
        package
    )
    if graph is None:
        log.info(f"{package.name} {package.version} has no children scoring directly")
        store_package_report(score_package(package.name, package.version, []))
    else:
        g, nodes = get_networkx_graph_and_nodes(graph)
        log.info(
            f"{package.name} {package.version} scoring from graph id={graph.id} ({len(g.edges)} edges, {len(g.nodes)} nodes)"
        )
        store_package_reports(score_package_and_children(g, nodes))


@app.task()
def scan_npm_package_then_build_report_tree(
    package_name: str, package_version: Optional[str] = None
) -> celery.result.AsyncResult:
    return scan_npm_package.apply_async(
        args=(package_name, package_version), link=build_report_tree.signature()
    )


async def fetch_package_data(
    fetcher: Callable[[argparse.Namespace, List[str], int], Dict],
    args: argparse.Namespace,
    package_names: List[str],
) -> Dict:
    async for package_result in fetcher(args, package_names, len(package_names)):
        if isinstance(package_result, Exception):
            raise package_result

        # TODO: return multiple results
        return package_result


@app.task()
def check_package_name_in_npmsio(package_name: str) -> bool:
    npmsio_score = asyncio.run(
        fetch_package_data(fetch_npmsio_scores, _NPMSIO_CLIENT_CONFIG, [package_name]),
        debug=False,
    )
    log.info(f"package: {package_name} on npms.io? {npmsio_score is not None}")
    log.info(f"saving npms.io score for {package_name}")
    # inserts a unique entry for new analyzed_at fields
    models.insert_npmsio_score(npmsio_score)
    return npmsio_score is not None


@app.task()
def check_package_in_npm_registry(
    package_name: str, package_version: Optional[str] = None
) -> Dict:
    npm_registry_entry = asyncio.run(
        fetch_package_data(
            fetch_npm_registry_metadata, _NPM_CLIENT_CONFIG, [package_name]
        ),
        debug=False,
    )

    package_name_exists = npm_registry_entry is not None
    if package_name_exists:
        # inserts new entries for new versions (but doesn't update old ones)
        log.info(f"saving npm registry entry for {package_name}")
        models.insert_npm_registry_entry(npm_registry_entry)

    log.info(f"package: {package_name} on npm registry? {package_name_exists}")
    if package_version is not None:
        package_version_exists = npm_registry_entry.get("versions", {}).get(
            package_version, False
        )
        log.info(
            f"package: {package_name}@{package_version!r} on npm registry? {package_version_exists}"
        )
        return package_name_exists and package_version_exists
    return package_name_exists


@app.task()
def check_npm_package_exists(
    package_name: str, package_version: Optional[str] = None
) -> bool:
    """
    Check that an npm package name has a score on npms.io and is published on
    the npm registry if a version is provided check that it's in the npm registry
    """
    # check npms.io first because it's usually faster (smaller response sizes)
    return check_package_name_in_npmsio(package_name) and check_package_in_npm_registry(
        package_name, package_version
    )


# list tasks for the web server to register against its flask app
tasks = [
    add,
    build_report_tree,
    check_npm_package_exists,
    check_package_in_npm_registry,
    check_package_name_in_npmsio,
    scan_npm_package,
    scan_npm_package_then_build_report_tree,
    score_package,
]
