import json
import logging
from random import randrange
from typing import AsyncGenerator

from flask import current_app

import depobs.database.models as models
import depobs.worker.scoring as scoring
import depobs.worker.serializers as serializers

from depobs.worker import k8s
from depobs.worker.tasks.fetch_npm_package_data import (
    fetch_missing_npm_data,
)
from depobs.worker.scan_config import ScanConfig


log = logging.getLogger(__name__)


class NPMDepFilesScan(ScanConfig):
    """
    Scan and score dependencies from a manifest file and one or more optional lockfiles
    """

    @staticmethod
    async def job_configs(
        scan: models.Scan,
    ) -> AsyncGenerator[k8s.KubeJobConfig, None]:
        job_name = f"scan-{scan.id}-depfiles-{hex(randrange(1 << 32))[2:]}"
        config = dict(
            **current_app.config["SCAN_JOB_CONFIGS"][scan.name],
            name=job_name,
        )
        yield {
            "backoff_limit": config["backoff_limit"],
            "context_name": config["context_name"],
            "name": config["name"],
            "namespace": config["namespace"],
            "image_name": config["image_name"],
            "args": config["args"],
            "env": {
                **config["env"],
                "JOB_NAME": config["name"],
                "SCAN_ID": str(scan.id),
                "DEP_FILE_URLS_JSON": json.dumps(list(scan.dep_file_urls())),
            },
            "secrets": config["secrets"],
            "service_account_name": config["service_account_name"],
            "volume_mounts": config["volume_mounts"],
        }

    @staticmethod
    async def save_results(scan: models.Scan) -> None:
        """
        Take scan pubsub results, deserializes and saves them, and updates the scan graph_ids.
        """
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
                db_graph: models.PackageGraph = deserialized[0]
                assert db_graph.id
                models.save_scan_with_graph_ids(scan, [db_graph.id])

    @staticmethod
    async def score_packages(
        scan: models.Scan,
    ) -> AsyncGenerator[models.PackageReport, None]:
        log.info(
            f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
        )
        await fetch_missing_npm_data()

        # TODO: handle non-lib package; list all top level packages and score them on the graph?
        # TODO: handle a library package score as usual (make sure we don't pollute the package version entry)
        # TODO: score the graph without a root package_version
        log.info(f"scan: {scan.id} scoring packages from scan graph {scan.graph_id}")
        for graph in scan.generate_package_graphs():
            for package_report in scoring.score_package_graph(graph).values():
                yield package_report
