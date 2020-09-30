import asyncio
import logging
from typing import (
    Optional,
)

import flask

from depobs.database.enums import ScanStatusEnum
import depobs.database.models as models

from depobs.util.traceback_util import exc_to_str
from depobs.worker import scans


log = logging.getLogger(__name__)


async def run_next_scan(app: flask.Flask) -> Optional[models.Scan]:
    """
    Async task that:

    * fetches the next scan job (returns None when one isn't found)

    Returns the updated scan or None (when one isn't found to run).
    """
    # try to read the next queued scan from the scans table if we weren't given one
    log.debug("checking for a scan in the DB to run")
    maybe_next_scan: Optional[models.Scan] = models.get_next_scan_with_status_query(
        status=ScanStatusEnum["queued"]
    ).first()
    if maybe_next_scan is None:
        log.debug("could not find a scan in the DB to run")
        await asyncio.sleep(5)
        return None
    return await run_scan(app, maybe_next_scan)


async def run_scan(
    app: flask.Flask,
    scan: models.Scan,
) -> models.Scan:
    """
    Async task that:

    * takes a scan job
    * starts a k8s job in the untrusted jobs cluster
    * updates the scan status from 'queued' to 'started'
    * watches the k8s job and sets the scan status to 'failed' or 'succeeded' when the k8s job finishes

    Returns the updated scan.
    """
    if not (
        isinstance(scan.params, dict)
        and all(k in scan.params.keys() for k in {"name", "args", "kwargs"})
    ):
        log.info(f"ignoring pending scan {scan.id} with params {scan.params}")
        return scan

    assert scan.name in {
        "scan_score_npm_dep_files",
        "scan_score_npm_package",
    }
    scan_fn = getattr(scans, scan.name)
    if scan.name != scan_fn.__name__:
        raise NotImplementedError(f"Scan of type {scan.name} not implemented")

    log.info(
        f"starting a k8s job for {scan.name} scan {scan.id} with params {scan.params} using {scan_fn}"
    )
    with app.app_context():
        scan = models.save_scan_with_status(scan, ScanStatusEnum["started"])
        # scan fails if any of its tarball scan jobs, data fetching, or scoring steps fail
        try:
            await scan_fn(scan)
            new_scan_status = ScanStatusEnum["succeeded"]
        except Exception as err:
            log.error(f"{scan.id} error scanning and scoring: {err}\n{exc_to_str()}")
            new_scan_status = ScanStatusEnum["failed"]
        return models.save_scan_with_status(scan, new_scan_status)
