import asyncio
import logging
from typing import Dict


from depobs.database.enums import ScanStatusEnum
import depobs.database.models as models

from depobs.util.traceback_util import exc_to_str
from depobs.worker import k8s
from depobs.worker.scans import *


log = logging.getLogger(__name__)


async def start_next_scan(_, backoff_seconds: int = 5) -> None:
    """
    Async task that
    * fetches the next 'queued' scan
    * starts a k8s job
    * updates the scan status to 'started'
    Returns the updated scan or None (when a scan isn't found to start).

    Requires depobs flask app context.
    """
    scan = models.get_next_scan_with_status_query(ScanStatusEnum["queued"]).first()
    if not scan:
        await asyncio.sleep(backoff_seconds)
        return None

    await start_scan(scan)


async def start_scan(
    scan: models.Scan,
) -> models.Scan:
    """
    Async task that:
    * takes a scan job
    * starts one or more k8s jobs in the untrusted jobs cluster
    * updates the scan status from 'queued' to 'started' and adds k8s job_names

    and returns the updated scan.

    Run in a flask app context.
    """
    try:
        if not (
            isinstance(scan.params, dict)
            and all(k in scan.params.keys() for k in {"name", "args", "kwargs"})
        ):
            raise Exception(f"queued scan {scan.id} has invalid params {scan.params}")

        scan_config = scan_type_to_config(scan.name)
        log.info(
            f"starting k8s jobs for {scan.name} scan {scan.id} with params {scan.params}"
        )

        job_configs: Dict[str, k8s.KubeJobConfig] = {}
        async for job_config in scan_config.job_configs(scan):
            job_configs[job_config["name"]] = job_config

        models.save_scan_with_job_names(scan, list(job_configs.keys()))
        for job_name, job_config in job_configs.items():
            log.info(
                f"scan {scan.id} starting k8s job {job_name} with config {job_config}"
            )
            k8s.create_job(job_config)
            log.info(f"scan {scan.id} started k8s job {job_name}")
        new_scan_status = ScanStatusEnum["started"]
    except Exception as err:
        log.error(f"{scan.id} error starting k8s jobs: {err}\n{exc_to_str()}")
        new_scan_status = ScanStatusEnum["failed"]

    started_scan = models.save_scan_with_status(scan, new_scan_status)
    assert started_scan.status in {
        ScanStatusEnum["started"],
        ScanStatusEnum["failed"],
    }
    log.info(f"scan {scan.id} updated status to {started_scan.status}")
    return started_scan
