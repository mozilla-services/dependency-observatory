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
    Iterable,
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

from depobs.website.do import create_celery_app
import depobs.database.models as models
from depobs.database.models import (
    NPMRegistryEntry,
    PackageReport,
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
)

from depobs.worker.scoring import score_package, score_package_and_children
import depobs.worker.validators as validators

# import exc_to_str to resolve import cycle for the following depobs.scanner.clients
from depobs.scanner.pipelines.util import exc_to_str as _
from depobs.scanner.clients.npmsio import fetch_npmsio_scores
from depobs.scanner.clients.npm_registry import fetch_npm_registry_metadata
from depobs.database.models import (
    PackageVersion,
    PackageGraph,
)
import depobs.scanner.graph_util as graph_util
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

    # fetch npm registry entry from DB
    for (
        package_version,
        source_url,
        git_head,
        tarball_url,
    ) in models.get_npm_registry_entries_to_scan(package_name, package_version):
        log.info(
            f"scanning {package_name}@{package_version} with {source_url}#{git_head} or {tarball_url}"
        )

        # we need a source_url and git_head or a tarball url to install
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

                fetch_and_save_npmsio_scores(
                    row[0]
                    for row in models.get_package_names_with_missing_npms_io_scores()
                    if row is not None
                )
        elif source_url and git_head:
            # TODO: port scanner find_dep_files and run_repo_tasks pipelines as used in analyze_package.sh
            raise NotImplementedError(
                f"Installing from VCS source and ref not implemented to scan {package_name}@{package_version}"
            )

    return (package_name, package_version)


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

    db_graph: Optional[PackageGraph] = get_latest_graph_including_package_as_parent(
        package
    )
    if db_graph is None:
        log.info(f"{package.name} {package.version} has no children scoring directly")
        store_package_report(score_package(package.name, package.version, []))
    else:
        g: nx.DiGraph = graph_util.package_graph_to_networkx_graph(db_graph)
        graph_util.update_node_attrs(
            g,
            package_version=db_graph.distinct_package_versions_by_id,
            label={
                pv.id: f"{pv.name}@{pv.version}"
                for pv in db_graph.distinct_package_versions_by_id.values()
            },
            npmsio_score=db_graph.get_npmsio_scores_by_package_version_id(),
            registry_entry=db_graph.get_npm_registry_data_by_package_version_id(),
        )
        log.info(
            f"{package.name} {package.version} scoring from graph id={db_graph.id} ({len(g.edges)} edges, {len(g.nodes)} nodes)"
        )
        store_package_reports(
            score_package_and_children(g, db_graph.distinct_package_versions_by_id)
        )


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
) -> List[Dict]:
    package_results = []
    async for package_result in fetcher(args, package_names, len(package_names)):
        if isinstance(package_result, Exception):
            raise package_result
        package_results.append(package_result)

    return package_results


@app.task()
def fetch_and_save_npmsio_scores(package_names: Iterable[str]) -> None:
    package_names = list(package_names)
    log.info(f"fetching npmsio scores for {len(package_names)} package names")
    log.debug(f"fetching npmsio scores for package names: {list(package_names)}")
    npmsio_scores: List[Dict] = asyncio.run(
        fetch_package_data(
            fetch_npmsio_scores,
            argparse.Namespace(**current_app.config["NPMSIO_CLIENT"]),
            package_names,
        ),
        debug=False,
    )
    if len(npmsio_scores) != len(package_names):
        log.info(
            f"only fetched {len(npmsio_scores)} scores for {len(package_names)} package names"
        )
    else:
        log.info(
            f"fetched {len(npmsio_scores)} scores for {len(package_names)} package names"
        )
    models.insert_npmsio_scores(score for score in npmsio_scores if score is not None)


@app.task()
def fetch_package_entry_from_registry(
    package_name: str, package_version: Optional[str] = None
) -> Optional[Dict]:
    npm_registry_entries = asyncio.run(
        fetch_package_data(
            fetch_npm_registry_metadata,
            argparse.Namespace(**current_app.config["NPM_CLIENT"]),
            [package_name],
        ),
        debug=False,
    )
    package_name_exists = (
        npm_registry_entries is not None and npm_registry_entries[0] is not None
    )
    log.info(f"package: {package_name} on npm registry? {package_name_exists}")
    if package_name_exists:
        # inserts new entries for new versions (but doesn't update old ones)
        log.info(f"saving npm registry entry for {package_name}")
        models.insert_npm_registry_entry(npm_registry_entries[0])
    return npm_registry_entries[0]


# list tasks for the web server to register against its flask app
tasks = [
    add,
    build_report_tree,
    fetch_package_entry_from_registry,
    scan_npm_package,
    scan_npm_package_then_build_report_tree,
]
