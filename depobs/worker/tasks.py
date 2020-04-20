import argparse
import asyncio
from collections import ChainMap
import datetime
import json
import os
from random import randrange
import sys
from typing import (
    AbstractSet,
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Union,
)
import logging

import celery
from celery.utils.log import get_task_logger
import celery.result
from flask import current_app
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
from depobs.scanner.pipelines.postprocess import postprocess_task
from depobs.scanner.pipelines.run_repo_tasks import (
    iter_task_envs,
    build_images_for_envs,
    run_task as run_repo_task,  # try to avoid confusing with celery tasks
)
from depobs.scanner.pipelines.save_to_db import (
    insert_package_graph,
    insert_package_audit,
)
import depobs.scanner.docker.containers as containers
from depobs.scanner.models.language import (
    ContainerTask,
    DockerImage,
    Language,
    PackageManager,
)

log = get_task_logger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)


app = create_celery_app()


@app.task()
def add(x, y):
    return x + y


async def scan_tarball_url(
    args: argparse.Namespace,
    tarball_url: str,
    package_name: Optional[str] = None,
    package_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Takes run_repo_tasks pipeline args and a tarball url and returns
    the run_repo_task result object (from running the repo tasks
    commands in a container).
    """
    task_envs: Tuple[
        Language, PackageManager, DockerImage, ChainMap, List[ContainerTask]
    ] = list(iter_task_envs(args))
    if args.docker_build:
        await build_images_for_envs(args, task_envs)

    assert len(task_envs) == 1
    for lang, pm, image, version_commands, container_tasks in task_envs:
        # TODO: add as new command in depobs.scanner.models.language?
        # write a package.json file to so npm audit doesn't error out
        container_tasks = [
            ContainerTask(
                name="write_package_json",
                # \\ before " so shlex doesn't strip the "
                command=f"""bash -c "cat <<EOF > /tmp/package.json\n{{\\"dependencies\\": {{\\"{package_name}\\": \\"{package_version}\\"}} }}\nEOF" """,
                check=True,
            ),
            ContainerTask(
                name="check_package_json",
                command="""cat /tmp/package.json""",
                check=True,
            ),
        ] + container_tasks
        # TODO: handle this in depobs.scanner.models.language?
        # fixup install command to take the tarball URL
        for t in container_tasks:
            if t.name == "install" and t.command == "npm install --save=true":
                t.command = f"npm install --save=true {tarball_url}"

        if args.dry_run:
            log.info(
                f"for {lang.name} {pm.name} would run in {image.local.repo_name_tag}"
                f" {list(version_commands.values())} concurrently then"
                f" {[t.command for t in tasks]} "
            )
            continue

        # TODO: reuse flask request ID or celery task id
        # use a unique container names to avoid conflicts
        container_name = f"dependency-observatory-scanner-scan_tarball_url-{hex(randrange(1 << 32))[2:]}"

        async with containers.run(
            image.local.repo_name_tag, name=container_name, cmd="/bin/bash",
        ) as c:
            # NB: running in /app will fail when /app is mounted for local
            version_results = await asyncio.gather(
                *[
                    containers.run_container_cmd_no_args_return_first_line_or_none(
                        command, c, working_dir="/tmp"
                    )
                    for command in version_commands.values()
                ]
            )
            versions = {
                command_name: version_results[i]
                for (i, (command_name, command)) in enumerate(version_commands.items())
            }

            task_results = [
                await run_repo_task(c, task, "/tmp", container_name)
                for task in container_tasks
            ]
            for tr in task_results:
                if isinstance(tr, Exception):
                    log.error(f"error running container task: {tr}")

            result: Dict[str, Any] = dict(
                versions=versions,
                task_results=[tr for tr in task_results if isinstance(tr, dict)],
            )
            return result


@app.task(bind=True)
def scan_npm_package(
    self: celery.Task, package_name: str, package_version: Optional[str] = None
) -> None:
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

    # assumes an NPM registry entry
    # fetch npm registry entry from DB
    query = (
        models.db.session.query(
            NPMRegistryEntry.package_version,
            NPMRegistryEntry.source_url,
            NPMRegistryEntry.git_head,
            NPMRegistryEntry.tarball,
        ).filter_by(package_name=package_name)
        # .order_by(NPMRegistryEntry.published_at.desc)
    )

    # filter for indicated version (if any)
    if package_version:
        query = query.filter_by(package_version=package_version)

    # we need a source_url and git_head or a tarball url to install
    for (package_version, source_url, git_head, tarball_url) in query.all():
        log.info(
            f"scanning {package_name}@{package_version} with {source_url}#{git_head} or {tarball_url}"
        )
        if tarball_url:
            # start an npm container, install the tarball, run list and audit
            # assert tarball_url == f"https://registry.npmjs.org/{package_name}/-/{package_name}-{package_version}.tgz
            container_task_results = asyncio.run(
                scan_tarball_url(
                    argparse.Namespace(**current_app.config["SCAN_NPM_TARBALL_ARGS"]),
                    tarball_url,
                    package_name,
                    package_version,
                )
            )
            log.info(f"got container task results for {package_name}@{package_version}")
            log.debug(f"got container task results:\n{container_task_results}")
            for task_result in container_task_results["task_results"]:
                postprocessed_container_task_result: Optional[
                    Dict[str, Any]
                ] = postprocess_task(task_result, {"list_metadata", "audit"})
                if not postprocessed_container_task_result:
                    continue

                task_data = postprocessed_container_task_result
                task_name = task_data["name"]
                if task_name == "list_metadata":
                    insert_package_graph(models.db.session, task_data)
                elif task_name == "audit":
                    insert_package_audit(models.db.session, task_data)
                else:
                    log.warning(f"skipping unrecognized task {task_name}")

        elif source_url and git_head:
            # TODO: port scanner find_dep_files and run_repo_tasks pipelines as used in analyze_package.sh
            raise NotImplementedError(
                f"Installing from VCS source and ref not implemented to scan {package_name}@{package_version}"
            )

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
        fetch_package_data(
            fetch_npmsio_scores,
            argparse.Namespace(**current_app.config["NPMSIO_CLIENT"]),
            [package_name],
        ),
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
            fetch_npm_registry_metadata,
            argparse.Namespace(**current_app.config["NPM_CLIENT"]),
            [package_name],
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
