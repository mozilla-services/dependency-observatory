import asyncio
import copy
import json
import logging
from random import randrange

from flask import current_app
import kubernetes

import depobs.database.models as models
from depobs.database.models import (
    store_package_reports,
)
import depobs.worker.scoring as scoring
import depobs.worker.serializers as serializers

from depobs.worker import k8s
from depobs.worker.tasks.fetch_npm_package_data import (
    fetch_missing_npm_data,
)
from depobs.worker.scan_util import RunRepoTasksConfig, run_job_to_completion


log = logging.getLogger(__name__)


async def scan_score_npm_dep_files(
    scan: models.Scan,
) -> None:
    """
    Scan and score dependencies from a manifest file and one or more optional lockfiles
    """
    log.info(f"scan: {scan.id} {scan.name} starting")
    config: RunRepoTasksConfig = copy.deepcopy(
        current_app.config["SCAN_NPM_DEP_FILES_ARGS"]
    )
    job_name = config["name"] = f"scan-{scan.id}-depfiles-{hex(randrange(1 << 32))[2:]}"
    task: asyncio.Task = asyncio.create_task(
        scan_npm_dep_files(
            config,
            scan,
        ),
        name=job_name,
    )
    job: kubernetes.client.models.v1_job.V1Job = await task
    log.info(f"scan: {scan.id} {job_name} k8s job finished with status {job.status}")
    if not job.status.succeeded:
        raise Exception(f"scan: {scan.id} {job_name} did not succeed")

    # wait for logs to show up from pubsub
    while True:
        log.info(f"scan: {scan.id} {job_name} succeeded; waiting for pubsub logs")
        if any(
            result.data["data"][-1]["type"] == "task_complete"
            for result in models.get_scan_job_results(job_name)
        ):
            break
        await asyncio.sleep(5)

    db_graph: models.PackageGraph
    log.info(f"scan: {scan.id} {job_name} saving job results")
    for deserialized in serializers.deserialize_scan_job_results(
        models.get_scan_job_results(k8s.get_job_env_var(job, "JOB_NAME"))
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

    log.info(
        f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
    )
    await fetch_missing_npm_data()

    # TODO: handle non-lib package; list all top level packages and score them on the graph?
    # TODO: handle a library package score as usual (make sure we don't pollute the package version entry)
    # TODO: score the graph without a root package_version
    assert db_graph
    store_package_reports(list(scoring.score_package_graph(db_graph).values()))


async def scan_npm_dep_files(
    config: RunRepoTasksConfig,
    scan: models.Scan,
) -> kubernetes.client.models.v1_job.V1Job:
    """
    Takes a run_repo_tasks config and scan_id.

    Returns the k8s job when it finishes
    """
    log.info(f"scan: {scan.id} scanning dep files with config {config}")
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
            "INSTALL_TARGET": ".",
            "JOB_NAME": config["name"],
            "SCAN_ID": str(scan.id),
            "DEP_FILE_URLS_JSON": json.dumps(list(scan.dep_file_urls())),
        },
        "secrets": config["secrets"],
        "service_account_name": config["service_account_name"],
        "volume_mounts": config["volume_mounts"],
    }
    return await run_job_to_completion(job_config, scan.id)
