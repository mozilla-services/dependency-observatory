import logging
from typing import AsyncGenerator, Callable

from depobs.database import models
from depobs.worker import k8s


log = logging.getLogger(__name__)


class ScanConfig:
    """
    Config for running a scan.
    """

    job_configs: Callable[[models.Scan], AsyncGenerator[k8s.KubeJobConfig, None]]
    score_packages: Callable[[models.Scan], AsyncGenerator[models.PackageReport, None]]

    @staticmethod
    async def save_results(scan: models.Scan) -> None:
        raise NotImplementedError()
