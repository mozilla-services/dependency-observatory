import asyncio
import copy
import logging
from random import randrange
from typing import (
    Generator,
    List,
    Optional,
)

from flask import current_app
import kubernetes

import depobs.database.models as models
from depobs.database.models import (
    store_package_reports,
    get_most_recently_inserted_package_from_name_and_version,
    get_latest_graph_including_package_as_parent,
)
import depobs.worker.scoring as scoring
import depobs.worker.serializers as serializers
import depobs.worker.validators as validators

from depobs.database.models import (
    PackageGraph,
    PackageVersion,
)
from depobs.worker import k8s
from depobs.worker.tasks.fetch_npm_package_data import (
    fetch_missing_npm_data,
    fetch_and_save_npmsio_scores,
    fetch_and_save_registry_entries,
)
from depobs.worker.scan_util import RunRepoTasksConfig, run_job_to_completion


log = logging.getLogger(__name__)


async def scan_tarball_url(
    config: RunRepoTasksConfig,
    tarball_url: str,
    scan_id: int,
    package_name: str,
    package_version: Optional[str] = None,
) -> kubernetes.client.models.v1_job.V1Job:
    """
    Takes a run_repo_tasks config, tarball url, and optional package
    name and version.

    Returns the k8s job when it finishes
    """
    job_config: k8s.KubeJobConfig = {
        "backoff_limit": config["backoff_limit"],
        "context_name": config["context_name"],
        "name": config["name"],
        "namespace": config["namespace"],
        "image_name": config["image_name"],
        "args": config["repo_tasks"],
        "env": {
            **config["env"],
            "LANGUAGE": config["language"],
            "PACKAGE_MANAGER": config["package_manager"],
            "PACKAGE_NAME": package_name,
            "PACKAGE_VERSION": package_version or "unknown-package-version",
            # see: https://github.com/mozilla-services/dependency-observatory/issues/280#issuecomment-641588717
            "INSTALL_TARGET": ".",
            "JOB_NAME": config["name"],
            "SCAN_ID": str(scan_id),
        },
        "secrets": config["secrets"],
        "service_account_name": config["service_account_name"],
        "volume_mounts": config["volume_mounts"],
    }
    return await run_job_to_completion(job_config, scan_id)


def scan_package_tarballs(scan: models.Scan) -> Generator[asyncio.Task, None, None]:
    """Given a scan, uses its package name and optional version params, checks for matching npm
    registry entries and start k8s jobs to scan the tarball url for
    each version.

    Generates scan jobs with format asyncio.Task that terminate when
    the k8s finishes.

    When the version is 'latest' only scans the most recently published version of the package.
    """
    package_name: str = scan.package_name
    scan_package_version: Optional[str] = scan.package_version

    # fetch npm registry entries from DB
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
        # we need a source_url and git_head or a tarball url to install
        if entry.tarball:
            job_name = f"scan-{scan.id}-pkg-{hex(randrange(1 << 32))[2:]}"
            config: RunRepoTasksConfig = copy.deepcopy(
                current_app.config["SCAN_NPM_TARBALL_ARGS"]
            )
            config["name"] = job_name

            log.info(
                f"scan: {scan.id} scanning {package_name}@{entry.package_version} with {entry.tarball} with config {config}"
            )
            # start an npm container, install the tarball, run list and audit
            # assert entry.tarball == f"https://registry.npmjs.org/{package_name}/-/{package_name}-{entry.package_version}.tgz
            yield asyncio.create_task(
                scan_tarball_url(
                    config,
                    entry.tarball,
                    scan.id,
                    package_name,
                    entry.package_version,
                ),
                name=job_name,
            )
        elif entry.source_url and entry.git_head:
            # TODO: port scanner find_dep_files and run_repo_tasks pipelines as used in analyze_package.sh
            log.info(
                f"scan: {scan.id} scanning {package_name}@{entry.package_version} from {entry.source_url}#{entry.git_head} not implemented"
            )
            log.error(
                f"scan: {scan.id} Installing from VCS source and ref not implemented to scan {package_name}@{entry.package_version}"
            )

        if scan_package_version == "latest":
            log.info(
                "scan: {scan.id} latest version of package requested. Stopping after first release version"
            )
            break


async def scan_score_npm_package(scan: models.Scan) -> None:
    """
    Scan and score an npm package using params from the provided Scan model
    """
    package_name: str = scan.package_name
    package_version: Optional[str] = scan.package_version
    log.info(
        f"scan: {scan.id} fetching npms.io score and npm registry entry for {package_name}"
    )
    await asyncio.gather(
        fetch_and_save_registry_entries([package_name]),
        fetch_and_save_npmsio_scores([package_name]),
    )

    tarball_scans: List[asyncio.Task] = list(scan_package_tarballs(scan))
    log.info(f"scan: {scan.id} scanning {package_name} {len(tarball_scans)} versions")
    k8s_jobs: List[kubernetes.client.models.v1_job.V1Job] = await asyncio.gather(
        *tarball_scans
    )
    successful_jobs = [job for job in k8s_jobs if job.status.succeeded]
    log.info(
        f"scan: {scan.id} {len(k8s_jobs)} k8s jobs finished, {len(successful_jobs)}) succeeded"
    )

    # wait for logs to show up from pubsub
    successful_job_names = {
        k8s.get_job_env_var(job, "JOB_NAME") for job in successful_jobs
    }
    while True:
        jobs_completed = {
            job_name: any(
                result.data["data"][-1]["type"] == "task_complete"
                for result in models.get_scan_job_results(job_name)
            )
            for job_name in successful_job_names
        }
        log.info(
            f"scan: {scan.id} {jobs_completed.keys()} finished; waiting for pubsub logs from {successful_job_names - set(jobs_completed.keys())}"
        )
        if set(jobs_completed.keys()) == successful_job_names:
            break
        await asyncio.sleep(5)

    log.info(f"scan: {scan.id} saving logs from {len(successful_jobs)} successful jobs")
    for job in successful_jobs:
        log.info(
            f"scan: {scan.id} saving job results for {k8s.get_job_env_var(job, 'PACKAGE_NAME')}@{k8s.get_job_env_var(job, 'PACKAGE_VERSION')}"
        )
        for deserialized in serializers.deserialize_scan_job_results(
            models.get_scan_job_results(k8s.get_job_env_var(job, "JOB_NAME"))
        ):
            models.save_deserialized(deserialized)

    log.info(
        f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
    )
    await fetch_missing_npm_data()

    log.info(f"scan: {scan.id} scoring {len(successful_jobs)} package versions")
    for job in successful_jobs:
        package_name, package_version = (
            k8s.get_job_env_var(job, "PACKAGE_NAME"),
            k8s.get_job_env_var(job, "PACKAGE_VERSION"),
        )
        log.info(
            f"scan: {scan.id} scoring package version {package_name}@{package_version}"
        )

        package: Optional[
            PackageVersion
        ] = get_most_recently_inserted_package_from_name_and_version(
            package_name, package_version
        )
        if package is None:
            log.error(
                f"scan: {scan.id} PackageVersion not found for {package_name} {package_version}. Skipping scoring."
            )
            continue

        db_graph: Optional[PackageGraph] = get_latest_graph_including_package_as_parent(
            package
        )
        if db_graph is None:
            log.info(
                f"scan: {scan.id} {package.name} {package.version} has no children"
            )
            db_graph = PackageGraph(id=None, link_ids=[])
            db_graph.distinct_package_ids = set([package.id])

        store_package_reports(list(scoring.score_package_graph(db_graph).values()))
