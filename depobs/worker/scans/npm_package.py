import asyncio
import logging
from random import randrange
from typing import (
    AsyncGenerator,
    Generator,
    List,
    Optional,
)

from flask import current_app

import depobs.database.models as models
import depobs.worker.scoring as scoring
import depobs.worker.serializers as serializers
import depobs.worker.validators as validators
from depobs.worker import k8s
from depobs.worker.tasks.fetch_npm_package_data import (
    fetch_missing_npm_data,
)
from depobs.worker.scan_config import ScanConfig
from depobs.worker.tasks.fetch_npm_package_data import (
    fetch_and_save_npmsio_scores,
    fetch_and_save_registry_entries,
)


log = logging.getLogger(__name__)


async def package_release_versions(
    scan: models.Scan,
) -> AsyncGenerator[models.NPMRegistryEntry, None]:
    package_name: str = scan.package_name
    scan_package_version: Optional[str] = scan.package_version

    await asyncio.gather(
        fetch_and_save_registry_entries([package_name]),
        fetch_and_save_npmsio_scores([package_name]),
    )

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

        yield entry

        if scan_package_version == "latest":
            log.info(
                f"scan: {scan.id} latest version of package requested. Stopping after first release version"
            )
            break


def score_package_version(
    scan: models.Scan, package_name: str, package_version: str
) -> Generator[models.PackageReport, None, None]:
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

    for package_report in scoring.score_package_graph(db_graph).values():
        yield package_report


class NPMPackageScan(ScanConfig):
    """
    Scan and score one or more release versions of a package from a registry
    """

    @staticmethod
    async def job_configs(scan: models.Scan) -> AsyncGenerator[k8s.KubeJobConfig, None]:
        async for entry in package_release_versions(scan):
            # we need a source_url and git_head or a tarball url to install
            job_name = f"scan-{scan.id}-pkg-{hex(randrange(1 << 32))[2:]}"
            config = dict(
                **current_app.config["SCAN_JOB_CONFIGS"][scan.name],
                name=job_name,
            )
            yield {
                "backoff_limit": config["backoff_limit"],
                "context_name": config["context_name"],
                "name": job_name,
                "namespace": config["namespace"],
                "image_name": config["image_name"],
                "args": config["args"],
                "env": {
                    **config["env"],
                    "PACKAGE_NAME": scan.package_name,
                    "PACKAGE_VERSION": entry.package_version
                    or "unknown-package-version",
                    "JOB_NAME": config["name"],
                    "SCAN_ID": str(scan.id),
                },
                "secrets": config["secrets"],
                "service_account_name": config["service_account_name"],
                "volume_mounts": config["volume_mounts"],
            }

    @staticmethod
    async def save_results(scan: models.Scan) -> None:
        log.info(f"scan: {scan.id} saving job results")
        db_graph_ids: List[int] = []
        for job_name in scan.job_names:
            for result in models.get_scan_results_by_job_name(job_name):
                package_name = result.data["data"][0]["envvar_args"]["PACKAGE_NAME"]
                package_version = result.data["data"][0]["envvar_args"][
                    "PACKAGE_VERSION"
                ]
                log.info(
                    f"scan: {scan.id} saving job {job_name} results for {package_name}@{package_version}"
                )
                for deserialized in serializers.deserialize_scan_job_results([result]):
                    models.save_deserialized(deserialized)
                    if isinstance(deserialized, tuple) and isinstance(
                        deserialized[0], models.PackageGraph
                    ):
                        db_graph: models.PackageGraph = deserialized[0]
                        assert db_graph.id
                        log.info(
                            f"scan: {scan.id} adding job {job_name} graph {db_graph.id}"
                        )
                        db_graph_ids.append(db_graph.id)
        models.save_scan_with_graph_ids(scan, db_graph_ids)

    @staticmethod
    async def score_packages(
        scan: models.Scan,
    ) -> AsyncGenerator[models.PackageReport, None]:
        log.info(
            f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
        )
        await fetch_missing_npm_data()

        package_versions = set(
            [
                result.data["data"][0]["envvar_args"]["PACKAGE_VERSION"]
                for job_name in scan.job_names
                for result in models.get_scan_results_by_job_name(job_name)
            ]
        )

        log.info(f"scan: {scan.id} scoring {len(package_versions)} package versions")
        for package_version in package_versions:
            for package_report in score_package_version(
                scan, scan.package_name, package_version
            ):
                yield package_report
