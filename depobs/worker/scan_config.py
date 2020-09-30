import logging
from typing import Generator, Iterable

from depobs.database import models
from depobs.worker import k8s


log = logging.getLogger(__name__)


class ScanConfig:
    """
    Abstract config for running a scan.
    """

    @staticmethod
    def job_configs(scan: models.Scan) -> Generator[k8s.KubeJobConfig, None, None]:
        raise NotImplementedError()

    @staticmethod
    async def save_results(scan: models.Scan) -> None:
        raise NotImplementedError()

    @staticmethod
    async def score_packages(scan: models.Scan) -> Iterable[models.PackageReport]:
        raise NotImplementedError()
