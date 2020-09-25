import asyncio
import copy
from datetime import timedelta
import json
import logging
from random import randrange
from typing import (
    AbstractSet,
    Any,
    AsyncGenerator,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    TypedDict,
    Union,
)


import flask
from flask import current_app
import kubernetes

import depobs.database.models as models
from depobs.util.traceback_util import exc_to_str
from depobs.worker import k8s
import depobs.worker.scoring as scoring
import depobs.worker.serializers as serializers
from depobs.worker.package_data import (
    fetch_missing_npm_data,
    fetch_and_save_npmsio_scores,
    fetch_and_save_registry_entries,
)
from depobs.worker import validators


log = logging.getLogger(__name__)


async def start_scan_jobs(
    app: flask.Flask,
    scan: models.Scan,
) -> models.Scan:
    """
    Async task that:

    * takes a scan job
    * starts one or more k8s jobs in the untrusted jobs cluster
    * updates the scan status from 'queued' to 'started'

    Returns the updated scan.
    """
    if not (
        isinstance(scan.params, dict)
        and all(k in scan.params.keys() for k in {"name", "args", "kwargs"})
    ):
        log.info(f"ignoring pending scan {scan.id} with params {scan.params}")
        return scan

    log.info(
        f"starting k8s jobs for {scan.name} scan {scan.id} with params {scan.params}"
    )
    with app.app_context():
        jobs: List[kubernetes.client.models.v1_job.V1Job]
        try:
            if scan.name == "scan_score_npm_package":
                log.info(
                    f"scan: {scan.id} fetching npms.io score and npm registry entry for {scan.package_name}"
                )
                await asyncio.gather(
                    fetch_and_save_registry_entries([scan.package_name]),
                    fetch_and_save_npmsio_scores([scan.package_name]),
                )
                jobs = list(start_package_scans(scan))
            elif scan.name == "scan_score_npm_dep_files":
                jobs = [start_dep_files_scan(scan)]
            else:
                raise Exception(f"Unknown scan type: {scan.name}")
            scan.jobs_count = len(jobs)
            new_scan_status = "started"
        except Exception as err:
            log.error(f"{scan.id} error starting k8s jobs: {err}\n{exc_to_str()}")
            new_scan_status = "failed"
        return models.save_scan_with_status(scan, new_scan_status)


async def finish_scan(
    app: flask.Flask,
    scan: models.Scan,
) -> models.Scan:
    """
    Async task that:

    * takes a started scan job
    * checks if the scan data was saved
    * updates the scan status from 'started' to 'succeeded' or 'failed'

    Returns the updated scan.
    """
    try:
        if scan.jobs_count is None:
            raise Exception(f"scan {scan.id} missing a jobs_count")

        completed_jobs_count = models.get_scan_completed_jobs_count_query(scan.id)
        if completed_jobs_count == scan.jobs_count:
            # finish the scan
            if scan.name == "scan_score_npm_package":
                await finish_package_scan(scan)
            elif scan.name == "scan_score_npm_dep_files":
                await finish_dep_files_scan(scan)
            else:
                raise Exception(f"Unknown scan type: {scan.name}")
        elif scan.time_since_updated() > timedelta(minutes=15):
            raise Exception(
                f"scan {scan.id} timed out ({completed_jobs_count} jobs completed of {scan.k8s_jobs_count})"
            )
        # else wait for k8s jobs to finish and pubsub results to come in

        new_scan_status = "succeeded"
    except Exception as err:
        log.error(f"{scan.id} error scanning and scoring: {err}\n{exc_to_str()}")
        new_scan_status = "failed"
    return models.save_scan_with_status(scan, new_scan_status)


async def get_next_scan_with_status(
    scan_status: str,
    backoff_seconds: int = 5,
) -> Optional[models.Scan]:
    """
    Returns the next scan with a given status or backs off by
    backoff_seconds when one isn't found.
    """
    assert scan_status in models.scan_status_enum.enums
    # try to read the next queued scan from the scans table if we weren't given one
    log.debug(f"checking for a scan in the DB with status {scan_status}")
    maybe_next_scan: Optional[models.Scan] = (
        models.get_next_scan().filter_by(status=scan_status).limit(1).one_or_none()
    )
    if maybe_next_scan is None:
        log.debug(f"could not find a scan with status {scan_status} in the DB")
        await asyncio.sleep(backoff_seconds)
        return None
    return maybe_next_scan


async def start_next_scan(app: flask.Flask) -> Optional[models.Scan]:
    """
    Async task that

    * fetches the next 'queued' scan
    * starts a k8s job
    * updates the scan status to 'started'

    Returns the updated scan or None (when a scan isn't found to start).
    """
    with app.app_context():
        scan = await get_next_scan_with_status("queued")
        if not scan:
            return None

        started_scan = await start_scan_jobs(app, scan)
        # models.scan_status_enum
        assert started_scan.status in {
            models.scan_status_enum.enums.index(state)
            for state in ["started", "failed"]
        }
        return started_scan


async def finish_next_scan(app: flask.Flask) -> Optional[models.Scan]:
    """
    Async task that:

    * fetches the next scan with status started
    * checks whether the scan job wrote scan completed to the DB
    * when scan results are present scores and updates the scan status to 'succeeded'
    * if scan results are not found within a certain amount of time or scoring fails updates the scan status to 'failed'

    Returns the updated scan or None (when a scan isn't found to finish).
    """
    with app.app_context():
        scan = await get_next_scan_with_status("started")
        if not scan:
            return None

        finished_scan = await finish_scan(app, scan)
        assert finished_scan.status in {
            models.scan_status_enum.enums.index(state)
            for state in ["succeeded", "failed"]
        }
        return finished_scan


def start_dep_files_scan(
    scan: models.Scan,
) -> kubernetes.client.models.v1_job.V1Job:
    log.info(f"scan: {scan.id} {scan.name} starting")
    job_name = f"scan-{scan.id}-depfiles-{hex(randrange(1 << 32))[2:]}"
    job_config: k8s.KubeJobConfig = dict(
        **current_app.config["SCAN_JOB_CONFIGS"][scan.name],
        name=job_name,
    )
    job_config["env"].update(
        {
            "JOB_NAME": job_name,
            "SCAN_ID": str(scan.id),
            "DEP_FILE_URLS_JSON": json.dumps(list(scan.dep_file_urls())),
        }
    )
    log.info(f"scan {scan.id} starting job {job_name} with config {job_config}")
    return k8s.create_job(job_config)


def start_package_version_scan(
    scan: models.Scan,
    package_name: str,
    package_version: Optional[str] = None,
) -> kubernetes.client.models.v1_job.V1Job:
    """
    Takes a package scan package name and optional package version.

    Returns the k8s job after it is created
    """
    job_name = f"scan-{scan.id}-pkg-{hex(randrange(1 << 32))[2:]}"
    job_config: k8s.KubeJobConfig = dict(
        **current_app.config["SCAN_JOB_CONFIGS"][scan.name],
        name=job_name,
    )
    job_config["env"].update(
        {
            "JOB_NAME": job_name,
            "SCAN_ID": str(scan.id),
            "PACKAGE_NAME": package_name,
            "PACKAGE_VERSION": package_version or "unknown-package-version",
        }
    )
    log.info(
        f"scan {scan.id} starting job {job_name} for {package_name}@{package_version} with config {job_config}"
    )
    return k8s.create_job(job_config)


def start_package_scans(
    scan: models.Scan,
) -> Generator[kubernetes.client.models.v1_job.V1Job, None, None]:
    """Given a scan, uses its package name and optional version params, checks for matching npm
    registry entries and start k8s jobs to scan the tarball url for
    each version.

    Generates scan k8s jobs

    When the version is 'latest' only scans the most recently published version of the package.
    """
    package_name: str = scan.package_name
    scan_package_version: Optional[str] = scan.package_version
    for entry in scan.get_npm_registry_entries():
        if entry.package_version is None:
            log.warn(
                f"scan: {scan.id} skipping npm registry entry with null version {package_name}"
            )
            continue
        elif not validators.is_npm_release_package_version(entry.package_version):
            log.warn(
                f"scan: {scan.id} {package_name} skipping npm registry entry with pre-release version {entry.package_version!r}"
            )
            continue

        log.info(f"scan: {scan.id} scanning {package_name}@{entry.package_version}")
        # should have a source_url and git_head or a tarball url to install
        yield start_package_version_scan(scan, package_name, entry.package_version)

        if scan_package_version == "latest":
            log.info(
                "scan: {scan.id} latest version of package requested. Stopping after first release version"
            )
            break


async def save_dep_files_scan_results(scan: models.Scan) -> models.PackageGraph:
    db_graph: models.PackageGraph
    log.info(f"scan: {scan.id} saving job results")
    for deserialized in serializers.deserialize_scan_job_results(
        models.get_scan_results_by_id(scan.id)
    ):
        models.save_deserialized(deserialized)
        if isinstance(deserialized, tuple) and isinstance(
            deserialized[0], models.PackageGraph
        ):
            log.info(
                f"scan: {scan.id} saving job results for {list(scan.dep_file_urls())}"
            )
            db_graph = deserialized[0]
            assert db_graph.id
            models.save_scan_with_graph_id(scan, db_graph.id)
    return db_graph


async def finish_dep_files_scan(
    scan: models.Scan,
) -> None:
    """
    Save scan results and score dependencies from a manifest file and
    one or more optional lockfiles
    """
    db_graph = await save_dep_files_scan_results(scan)

    log.info(
        f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
    )
    await fetch_missing_npm_data()

    # TODO: handle non-lib package; list all top level packages and score them on the graph?
    # TODO: handle a library package score as usual (make sure we don't pollute the package version entry)
    # TODO: score the graph without a root package_version
    assert db_graph
    models.store_package_reports(list(scoring.score_package_graph(db_graph).values()))


async def score_package_version(
    scan: models.Scan, package_name: str, package_version: str
) -> None:
    log.info(
        f"scan: {scan.id} scoring package version {package_name}@{package_version}"
    )
    package: Optional[
        models.PackageVersion
    ] = models.get_most_recently_inserted_package_from_name_and_version(
        package_name, package_version
    )
    if package is None:
        log.error(
            f"scan: {scan.id} PackageVersion not found for {package_name} {package_version}. Skipping scoring."
        )
        return

    db_graph: Optional[
        models.PackageGraph
    ] = models.get_latest_graph_including_package_as_parent(package)
    if db_graph is None:
        log.info(f"scan: {scan.id} {package.name} {package.version} has no children")
        db_graph = models.PackageGraph(id=None, link_ids=[])
        db_graph.distinct_package_ids = set([package.id])

    models.store_package_reports(list(scoring.score_package_graph(db_graph).values()))


async def finish_package_scan(scan: models.Scan) -> None:
    """
    Save scan results and score dependencies for the npm package versions
    """
    package_name: str
    package_versions: Set[str] = set()
    for result in models.get_scan_results_by_id(scan.id).group_by(
        models.JSONResult.data["attributes"]["JOB_NAME"].as_string()
    ):
        package_name = result.data["attributes"]["PACKAGE_NAME"]
        package_version = result.data["attributes"]["PACKAGE_VERSION"]
        log.info(
            f"scan: {scan.id} saving job results for {package_name}@{package_version}"
        )
        for deserialized in serializers.deserialize_scan_job_results(result):
            models.save_deserialized(deserialized)
        package_versions.add(package_version)

    log.info(
        f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
    )
    await fetch_missing_npm_data()

    log.info(f"scan: {scan.id} scoring {len(package_versions)} package versions")
    for package_version in package_versions:
        score_package_version(scan, package_name, package_version)
