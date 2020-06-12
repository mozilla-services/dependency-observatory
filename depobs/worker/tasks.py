import asyncio
import logging
from random import randrange
from typing import (
    AbstractSet,
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
    TypedDict,
)

import celery
from celery.utils.log import get_task_logger
import celery.result
from flask import current_app
import kubernetes

from depobs.website.do import create_celery_app
import depobs.database.models as models
from depobs.database.models import (
    NPMRegistryEntry,
    PackageReport,
    get_package_report,
    get_npms_io_score,
    get_NPMRegistryEntry,
    get_maintainers_contributors,
    get_npm_registry_data,
    get_vulnerability_counts,
    store_package_report,
    store_package_reports,
    get_most_recently_inserted_package_from_name_and_version,
    get_latest_graph_including_package_as_parent,
    get_placeholder_entry,
)

import depobs.worker.scoring as scoring
import depobs.worker.serializers as serializers
import depobs.worker.validators as validators

# import exc_to_str to resolve import cycle for the following depobs.clients
from depobs.util.traceback_util import exc_to_str as _
from depobs.clients.npmsio import fetch_npmsio_scores, NPMSIOClientConfig
from depobs.clients.npm_registry import (
    fetch_npm_registry_metadata,
    NPMRegistryClientConfig,
)
from depobs.database.models import (
    PackageGraph,
    PackageVersion,
    insert_package_graph,
)
from depobs.util.type_util import Result
from depobs.worker import k8s


log = get_task_logger(__name__)


app = create_celery_app()


@app.task()
def add(x: int, y: int) -> int:
    return x + y


class RunRepoTasksConfig(TypedDict):
    # k8s namespace to create pods e.g. "default"
    namespace: str

    # Language to run commands for
    language: str

    # Package manager to run commands for
    package_manager: str

    # Run install, list_metadata, or audit tasks in the order
    # provided
    repo_tasks: List[str]

    # Docker image to run
    image_name: str


async def scan_tarball_url(
    config: RunRepoTasksConfig,
    tarball_url: str,
    package_name: Optional[str] = None,
    package_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Takes a run_repo_tasks config, tarball url, and optional package
    name and version

    returns
    """
    job_name = f"scan-tarball-url-{hex(randrange(1 << 32))[2:]}"
    job_config: k8s.KubeJobConfig = {
        "name": job_name,
        "namespace": config["namespace"],
        "image_name": config["image_name"],
        "args": config["repo_tasks"],
        "env": {
            "LANGUAGE": config["language"],
            "PACKAGE_MANAGER": config["package_manager"],
            "PACKAGE_NAME": package_name or "unknown-package-name",
            "PACKAGE_VERSION": package_version or "unknown-package-version",
            # see: https://github.com/mozilla-services/dependency-observatory/issues/280#issuecomment-641588717
            "INSTALL_TARGET": ".",
        },
    }

    def read_status(
        job_name: str, job_config: k8s.KubeJobConfig
    ) -> kubernetes.client.models.v1_job_status.V1JobStatus:
        # TODO: figure out status only perms for:
        # .read_namespaced_job_status(name=job_name, namespace=job_config["namespace"])
        return (
            client.BatchV1Api()
            .list_namespaced_job(
                namespace=job_config["namespace"],
                label_selector=f"job-name={job_name}",
            )
            .items[0]
            .status
        )

    client = k8s.get_client()
    with k8s.run_job(job_config) as job:
        log.info(f"started job {job}")
        await asyncio.sleep(1)

        status = read_status(job_name, job_config)
        log.info(f"got job status {status}")
        while True:
            if status.failed:
                log.error(f"k8s job {job_name} failed")
                raise Exception(f"k8s job {job_name} failed")
                break
            if status.succeeded:
                log.info(f"k8s job {job_name} succeeded")
                job_pod_name = (
                    client.CoreV1Api()
                    .list_namespaced_pod(
                        namespace=job_config["namespace"],
                        label_selector=f"job-name={job_name}",
                    )
                    .items[0]
                    .metadata.name
                )
                stdout = client.CoreV1Api().read_namespaced_pod_log(
                    name=job_pod_name, namespace=job_config["namespace"]
                )
                break
            if not status.active:
                log.error(f"k8s job {job_name} stopped")
                raise Exception(
                    f"k8s job {job_name} not active (did not fail or succeed)"
                )
                break

            await asyncio.sleep(1)
            status = read_status(job_name, job_config)
            log.info(f"got job status {status}")

    versions: Optional[Dict[str, str]] = None
    task_results: List[Dict[str, Any]] = []
    for stdout_line in stdout.split("\n"):
        line = serializers.parse_stdout_as_json(stdout_line.strip("\r"))
        if not isinstance(line, dict):
            continue
        if line.get("type", None) != "task_result":
            continue
        versions = versions or line.get("versions", None)
        line["container_name"] = job_name
        task_results.append(line)

    return dict(versions=versions, task_results=task_results)


@app.task(bind=True)
def scan_npm_package(
    self: celery.Task, package_name: str, package_version: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    package_name_validation_error = validators.get_npm_package_name_validation_error(
        package_name
    )
    if package_name_validation_error is not None:
        raise package_name_validation_error

    if package_version:
        package_version_validation_error = validators.get_npm_package_version_validation_error(
            package_version
        )
        if package_version_validation_error is not None:
            raise package_version_validation_error

    # fetch npm registry entry from DB
    for (
        package_version,
        source_url,
        git_head,
        tarball_url,
    ) in models.get_npm_registry_entries_to_scan(package_name, package_version):
        log.info(
            f"scanning {package_name}@{package_version} with {source_url}#{git_head} or {tarball_url}"
        )

        # we need a source_url and git_head or a tarball url to install
        if tarball_url:
            # start an npm container, install the tarball, run list and audit
            # assert tarball_url == f"https://registry.npmjs.org/{package_name}/-/{package_name}-{package_version}.tgz
            container_task_results: Dict[str, Any] = asyncio.run(
                scan_tarball_url(
                    current_app.config["SCAN_NPM_TARBALL_ARGS"],
                    tarball_url,
                    package_name,
                    package_version,
                )
            )
            log.info(f"got container task results for {package_name}@{package_version}")
            log.debug(f"got container task results:\n{container_task_results}")
            for task_result in container_task_results["task_results"]:
                serialized_container_task_result: Optional[
                    Dict[str, Any]
                ] = serializers.serialize_repo_task(
                    task_result, {"list_metadata", "audit"}
                )
                if not serialized_container_task_result:
                    continue

                task_data = serialized_container_task_result
                task_name = task_data["name"]
                if task_name == "list_metadata":
                    insert_package_graph(task_data)
                elif task_name == "audit":

                    for (
                        advisory_fields,
                        impacted_versions,
                    ) in serializers.node_repo_task_audit_output_to_advisories_and_impacted_versions(
                        task_data
                    ):
                        advisory: models.Advisory = list(
                            serializers.serialize_advisories([advisory_fields])
                        )[0]
                        models.insert_advisories([advisory])
                        models.update_advisory_vulnerable_package_versions(
                            advisory, set(impacted_versions)
                        )
                else:
                    log.warning(f"skipping unrecognized task {task_name}")

                # TODO: use asyncio.gather to run these concurrently
                fetch_and_save_npmsio_scores(
                    row[0]
                    for row in models.get_package_names_with_missing_npms_io_scores()
                    if row is not None
                )
                fetch_and_save_registry_entries(
                    row[0]
                    for row in models.get_package_names_with_missing_npm_entries()
                    if row is not None
                )
        elif source_url and git_head:
            # TODO: port scanner find_dep_files and run_repo_tasks pipelines as used in analyze_package.sh
            raise NotImplementedError(
                f"Installing from VCS source and ref not implemented to scan {package_name}@{package_version}"
            )

    return (package_name, package_version)


@app.task()
def build_report_tree(package_version_tuple: Tuple[str, str]) -> None:
    package_name, package_version = package_version_tuple

    package: Optional[
        PackageVersion
    ] = get_most_recently_inserted_package_from_name_and_version(
        package_name, package_version
    )
    if package is None:
        pr = get_placeholder_entry(package_name, package_version)
        if pr:
            pr.status = "error"
            store_package_report(pr)
        raise Exception(
            f"PackageVersion not found for {package_name} {package_version}."
        )

    db_graph: Optional[PackageGraph] = get_latest_graph_including_package_as_parent(
        package
    )
    if db_graph is None:
        log.info(f"{package.name} {package.version} has no children")
        db_graph = PackageGraph(id=None, link_ids=[])
        db_graph.distinct_package_ids = set([package.id])

    store_package_reports(list(scoring.score_package_graph(db_graph).values()))


@app.task()
def scan_npm_package_then_build_report_tree(
    package_name: str, package_version: Optional[str] = None
) -> celery.result.AsyncResult:
    return scan_npm_package.apply_async(
        args=(package_name, package_version), link=build_report_tree.signature()
    )


# fetch_package_data should take fetcher and config params with matching config
# types i.e. do not not let fetcher take an NPMSIOClientConfig with config
# NPMRegistryClientConfig
ClientConfig = TypeVar("ClientConfig", NPMSIOClientConfig, NPMRegistryClientConfig)


async def fetch_package_data(
    fetcher: Callable[
        [ClientConfig, Iterable[str], Optional[int]],
        AsyncGenerator[Result[Dict[str, Dict]], None],
    ],
    config: ClientConfig,
    package_names: List[str],
) -> List[Dict]:
    package_results = []
    # TODO: figure this type error out later
    async for package_result in fetcher(config, package_names, len(package_names)):  # type: ignore
        if isinstance(package_result, Exception):
            raise package_result
        package_results.append(package_result)

    return package_results


@app.task()
def fetch_and_save_npmsio_scores(package_names: Iterable[str]) -> List[Dict]:
    package_names = list(package_names)
    log.info(f"fetching npmsio scores for {len(package_names)} package names")
    log.debug(f"fetching npmsio scores for package names: {list(package_names)}")
    npmsio_scores: List[Dict] = asyncio.run(
        fetch_package_data(
            fetch_npmsio_scores, current_app.config["NPMSIO_CLIENT"], package_names,
        ),
        debug=False,
    )
    if len(npmsio_scores) != len(package_names):
        log.info(
            f"only fetched {len(npmsio_scores)} scores for {len(package_names)} package names"
        )
    else:
        log.info(
            f"fetched {len(npmsio_scores)} scores for {len(package_names)} package names"
        )
    models.insert_npmsio_scores(
        serializers.serialize_npmsio_scores(
            score for score in npmsio_scores if score is not None
        )
    )
    return npmsio_scores


@app.task()
def fetch_and_save_registry_entries(package_names: Iterable[str]) -> List[Dict]:
    package_names = list(package_names)
    log.info(f"fetching registry entries for {len(package_names)} package names")
    log.debug(f"fetching registry entries for package names: {list(package_names)}")
    npm_registry_entries = asyncio.run(
        fetch_package_data(
            fetch_npm_registry_metadata,
            current_app.config["NPM_CLIENT"],
            package_names,
        ),
        debug=False,
    )
    if len(npm_registry_entries) != len(package_names):
        log.info(
            f"only fetched {len(npm_registry_entries)} registry entries for {len(package_names)} package names"
        )
    else:
        log.info(
            f"fetched {len(npm_registry_entries)} registry entries for {len(package_names)} package names"
        )
    # inserts new entries for new versions (but doesn't update old ones)
    models.insert_npm_registry_entries(
        serializers.serialize_npm_registry_entries(
            registry_entry
            for registry_entry in npm_registry_entries
            if registry_entry is not None
        )
    )
    return npm_registry_entries
