import argparse
import asyncio
import datetime
import os
import sys
import re
import subprocess
from typing import AbstractSet, Callable, Dict, Generator, List, Optional, Tuple, Union
import logging

from celery import Celery
from celery.exceptions import (
    SoftTimeLimitExceeded,
    TimeLimitExceeded,
    WorkerLostError,
    WorkerShutdown,
    WorkerTerminate,
)
import celery.result
import networkx as nx
from networkx.algorithms.dag import descendants, is_directed_acyclic_graph

import depobs.worker.celeryconfig as celeryconfig

from depobs.website.models import (
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
    get_networkx_graph_and_nodes,
)

# import exc_to_str to resolve import cycle for the following fpr.clients
from fpr.pipelines.util import exc_to_str as _
from fpr.clients.npmsio import fetch_npmsio_scores
from fpr.clients.npm_registry import fetch_npm_registry_metadata

from fpr.db.schema import (
    Base,
    Advisory,
    PackageVersion,
    PackageLink,
    PackageGraph,
    NPMSIOScore,
    NPMRegistryEntry,
)

log = logging.getLogger("depobs.worker")
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

# http client config
# an npm registry access token for fetch_npm_registry_metadata. Defaults NPM_PAT env var. Should be read-only.
NPM_PAT = os.environ.get("NPM_PAT", None)

# celery will try to import these if they're public vars (no _ prefix)
_NPM_CLIENT_CONFIG = argparse.Namespace(
    user_agent="https://github.com/mozilla-services/dependency-observatory-scanner (foxsec+fpr@mozilla.com)",
    total_timeout=30,
    max_connections=1,
    max_retries=1,
    package_batch_size=1,
    dry_run=False,
    npm_auth_token=NPM_PAT,
)
_NPMSIO_CLIENT_CONFIG = argparse.Namespace(
    user_agent="https://github.com/mozilla-services/dependency-observatory-scanner (foxsec+fpr@mozilla.com)",
    total_timeout=10,
    max_connections=1,
    package_batch_size=1,
    dry_run=False,
)

# Create the scanner task queue
scanner = Celery(
    "tasks",
    broker=os.environ["CELERY_BROKER_URL"],
    result_backend=os.environ["CELERY_RESULT_BACKEND"],
)
scanner.config_from_object(celeryconfig)

# The name must be less than or equal to 214 characters. This includes the scope for scoped packages.
# The name can’t start with a dot or an underscore.
# New packages must not have uppercase letters in the name.
# The name ends up being part of a URL, an argument on the command line, and a folder name. Therefore, the name can’t contain any non-URL-safe characters.
#
# https://docs.npmjs.com/files/package.json#name
NPM_PACKAGE_NAME_RE = re.compile(
    r"""[@a-zA-Z0-9][\.-_@/a-zA-Z0-9]{0,213}""", re.VERBOSE,
)


def get_npm_package_name_validation_error(package_name: str) -> Optional[Exception]:
    """returns an Exception if package name is invalid or None if it is valid"""
    if not isinstance(package_name, str):
        return Exception("Invalid NPM package name. Must be a str.")

    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        return Exception(
            f"Invalid NPM package name. Must match {NPM_PACKAGE_NAME_RE.pattern!r}"
        )

    return None


# Version must be parseable by node-semver, which is bundled with npm as a dependency.
#
# https://docs.npmjs.com/files/package.json#version
#
# https://docs.npmjs.com/misc/semver#versions
NPM_PACKAGE_VERSION_RE = re.compile(
    r"""(=v)?           # strip leading = and v
[0-9]+\.[0-9]+\.[0-9]+  # major minor and patch versions (TODO: check if positive ints)
[-]?[-\.0-9A-Za-z]*       # optional pre-release version e.g. -alpha.1 (TODO: split out identifiers)
[+]?[-\.0-9A-Za-z]*       # optional build metadata e.g. +exp.sha.5114f85
""",
    re.VERBOSE,
)


def get_npm_package_version_validation_error(package_name: str) -> Optional[Exception]:
    """returns an Exception if package version is invalid or None if it is valid"""
    if not isinstance(package_name, str):
        return Exception("Invalid NPM package version. Must be a str.")

    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        return Exception(
            f"Invalid NPM package version. Must match {NPM_PACKAGE_VERSION_RE.pattern!r}"
        )

    return None


@scanner.task()
def add(x, y):
    return x + y


@scanner.task()
def scan_npm_package(
    package_name: str, package_version: Optional[str] = None
) -> None:
    package_name_validation_error = get_npm_package_name_validation_error(package_name)
    if package_name_validation_error is not None:
        raise package_name_validation_error

    if package_version:
        package_version_validation_error = get_npm_package_version_validation_error(
            package_version
        )
        if package_version_validation_error is not None:
            raise package_version_validation_error

    # mozilla/dependencyscan:latest must already be built/pulled/otherwise
    # present on the worker node
    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        f"DB_URL={os.environ['DATABASE_URI']}",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "mozilla/dependencyscan:latest",
        "analyze_package.sh",
        package_name,
    ]
    if package_version:
        command.append(package_version)

    log.info(f"running {command} for package_name {package_name}@{package_version}")
    subprocess.run(command, encoding="utf-8", capture_output=True).check_returncode()
    return (package_name, package_version)


@scanner.task()
def score_package(
    package_name: str,
    package_version: str,
    direct_dep_reports: List[PackageReport],
    all_deps_count: int=0,
) -> PackageReport:
    log.info(f"scoring package: {package_name}@{package_version} with direct deps {list((r.package, r.version) for r in direct_dep_reports)}")
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
    for package, version, severity, count in get_vulnerability_counts(package_name, package_version):
        log.info(f"scoring package: {package_name}@{package_version} found vulnerable dep: \t{package}\t{version}\t{severity}\t{count}")
        if severity == "critical":
            pr.directVulnsCritical_score = count
        elif severity == "high":
            pr.directVulnsHigh_score = count
        elif severity == "medium":
            pr.directVulnsMedium_score = count
        elif severity == "low":
            pr.directVulnsLow_score = count
        else:
            log.error(
                f"unexpected severity {severity} for package {package} / version {version}"
            )

    for published_at, maintainers, contributors in get_npm_registry_data(package_name, package_version):
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
        for severity in ('Critical', 'High', 'Medium', 'Low'):
            setattr(pr, f"indirectVulns{severity}_score",
                getattr(report, f"directVulns{severity}_score", 0) +
                getattr(report, f"indirectVulns{severity}_score", 0)
            )
        pr.dependencies.append(report)

    if dep_rep_count != pr.immediate_deps:
        log.error(
            f"expected {pr.immediate_deps} dependencies but got {dep_rep_count} for package {package_name} / version {package_version}"
        )

    pr.scoring_date = datetime.datetime.now()
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
        only_points_to_visited = set(node for node in points_to_visited if all(dst in visited for (_, dst) in g.out_edges(node)))
        new_only_points_to_visited = only_points_to_visited - visited
        if not bool(new_only_points_to_visited): # visited nothing new
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
                    for direct_dep_package_version_id in
                    g.successors(package_version_id)
                ],
                all_deps_count=len(descendants(g, package_version_id)),
            )

    return package_reports_by_id.values()

@scanner.task()
def build_report_tree(package_version_tuple: Tuple[str, str]) -> None:
    package_name, package_version = package_version_tuple

    package: Optional[PackageVersion] = get_most_recently_inserted_package_from_name_and_version(package_name, package_version)
    if package is None:
        raise Exception(f"PackageVersion not found for {package_name} {package_version}.")

    graph: Optional[PackageGraph] = get_latest_graph_including_package_as_parent(package)
    if graph is None:
        log.info(f"{package.name} {package.version} has no children scoring directly")
        store_package_report(score_package(package.name, package.version))
    else:
        g, nodes = get_networkx_graph_and_nodes(graph)
        log.info(f"{package.name} {package.version} scoring from graph id={graph.id} ({len(g.edges)} edges, {len(g.nodes)} nodes)")
        store_package_reports(score_package_and_children(g, nodes))


@scanner.task()
def scan_npm_package_then_build_report_tree(
    package_name: str, package_version: Optional[str] = None
) -> celery.result.AsyncResult:
    return scan_npm_package.apply_async(args=(package_name, package_version), link=build_report_tree.signature())


async def fetch_and_save_package_data(
    fetcher: Callable[[argparse.Namespace, List[str], int], Dict],
    args: argparse.Namespace,
    package_names: List[str]
) -> Dict:
    async for package_result in fetcher(args, package_names, len(package_names)):
        if isinstance(package_result, Exception):
            raise package_result
        # TODO: save to db
        # TODO: return multiple results
        return package_result


@scanner.task()
def check_package_name_in_npmsio(package_name: str) -> bool:
    npmsio_score = asyncio.run(fetch_and_save_package_data(fetch_npmsio_scores, _NPMSIO_CLIENT_CONFIG, [package_name]), debug=False)
    log.info(f"package: {package_name} on npms.io? {npmsio_score is not None}")
    return npmsio_score is not None


@scanner.task()
def check_package_in_npm_registry(package_name: str, package_version: Optional[str] = None) -> Dict:
    npm_registry_entry = asyncio.run(fetch_and_save_package_data(fetch_npm_registry_metadata, _NPM_CLIENT_CONFIG, [package_name]), debug=False)

    package_name_exists = npm_registry_entry is not None
    log.info(f"package: {package_name} on npm registry? {package_name_exists}")
    if package_version is not None:
        package_version_exists = npm_registry_entry.get("versions", {}).get(package_version, False)
        log.info(f"package: {package_name}@{package_version!r} on npm registry? {package_version_exists}")
        return package_name_exists and package_version_exists
    return package_name_exists


@scanner.task()
def check_npm_package_exists(package_name: str, package_version: Optional[str] = None) -> bool:
    """
    Check that an npm package name has a score on npms.io and is published on
    the npm registry if a version is provided check that it's in the npm registry
    """
    # check npms.io first because it's usually faster (smaller response sizes)
    return check_package_name_in_npmsio(package_name) and check_package_in_npm_registry(package_name, package_version)
