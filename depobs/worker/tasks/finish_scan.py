import asyncio
from datetime import timedelta
import logging


from depobs.database.enums import ScanStatusEnum
import depobs.database.models as models

from depobs.util.traceback_util import exc_to_str
from depobs.worker.scans import *

log = logging.getLogger(__name__)


async def finish_next_scan(_, backoff_seconds: int = 3) -> None:
    """
    Async task that:

    * fetches the next scan with status started
    * checks whether the scan job wrote scan completed to the DB
    * when scan results are present scores and updates the scan status to 'succeeded'
    * if scan results are not found within a certain amount of time or scoring fails updates the scan status to 'failed'
    Returns the updated scan or None (when a scan isn't found to finish).

    Requires depobs flask app context.
    """
    scan = models.get_next_scan_with_status_query(ScanStatusEnum["started"]).first()
    if not scan:
        log.debug(f"no scan found to finish sleeping for {backoff_seconds}")
        await asyncio.sleep(backoff_seconds)
        return None

    finished_scan = await finish_scan(scan)
    if finished_scan.status == scan.status:
        log.debug(
            f"scan {scan.id} status unchanged from {scan.status} sleeping for {backoff_seconds}"
        )
        await asyncio.sleep(backoff_seconds)
    else:
        log.info(
            f"scan {scan.id} updated status from {scan.status} to {finished_scan.status}"
        )


async def finish_scan(
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
        if not scan.job_names:
            raise Exception(f"scan {scan.id} has a falsy jobs_names")

        completed_jobs_count = models.get_scan_completed_jobs_query(scan.id).count()
        log.info(f"scan {scan.id} count {completed_jobs_count} completed jobs")
        if completed_jobs_count and completed_jobs_count == len(scan.job_names):
            scan_config = scan_type_to_config(scan.name)
            await scan_config.save_results(scan)
            async for package_report in scan_config.score_packages(scan):
                log.info(
                    f"scan {scan.id} saving package report {package_report.id} {package_report.package}@{package_report.version}"
                )
                models.store_package_reports([package_report])
        elif scan.get_time_since_updated() > timedelta(minutes=15):
            raise Exception(
                f"scan {scan.id} timed out ({completed_jobs_count} jobs completed of {scan.k8s_jobs_count})"
            )
        else:
            # wait for k8s jobs to finish and pubsub results to come in
            # and don't update the scan status
            return scan

        new_scan_status = ScanStatusEnum["succeeded"]
    except Exception as err:
        log.error(f"{scan.id} error scanning and scoring: {err}\n{exc_to_str()}")
        new_scan_status = ScanStatusEnum["failed"]

    finished_scan = models.save_scan_with_status(scan, new_scan_status)
    assert finished_scan.status in {
        ScanStatusEnum["succeeded"],
        ScanStatusEnum["failed"],
    }
    return finished_scan
