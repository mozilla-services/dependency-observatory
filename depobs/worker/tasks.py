import asyncio
import logging
import requests
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
    TypedDict,
)

from flask import current_app
import kubernetes

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
    save_json_results,
)
import depobs.worker.scoring as scoring
import depobs.worker.serializers as serializers
import depobs.worker.validators as validators

from depobs.clients.aiohttp_client import AIOHTTPClientConfig
from depobs.clients.hibp import fetch_hibp_breach_data
from depobs.clients.npmsio import fetch_npmsio_scores
from depobs.clients.npm_registry import fetch_npm_registry_metadata
from depobs.database.models import (
    PackageGraph,
    PackageVersion,
    insert_package_graph,
)
from depobs.util.type_util import Result
from depobs.worker import k8s

log = logging.getLogger(__name__)


class RunRepoTasksConfig(TypedDict):
    # k8s config context name to use (to access other clusters)
    context_name: str

    # k8s namespace to create pods e.g. "default"
    namespace: str

    # number of retries before marking this job failed
    backoff_limit: int

    # number of seconds the job completes or fails to delete it
    # 0 to delete immediately, None to never delete the job
    ttl_seconds_after_finished: Optional[int]

    # Language to run commands for
    language: str

    # Package manager to run commands for
    package_manager: str

    # Run install, list_metadata, or audit tasks in the order
    # provided
    repo_tasks: List[str]

    # Docker image to run
    image_name: str

    # k8s service account name to run the job pod with
    service_account_name: str


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
        "backoff_limit": config["backoff_limit"],
        "ttl_seconds_after_finished": config["ttl_seconds_after_finished"],
        "context_name": config["context_name"],
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
        "service_account_name": config["service_account_name"],
    }
    log.info(f"starting job {job_name} with config {job_config}")
    with k8s.run_job(job_config) as job:
        log.info(f"started job {job}")
        await asyncio.sleep(1)

        status = k8s.read_job_status(
            job_config["namespace"], job_name, context_name=job_config["context_name"]
        )
        log.info(f"got job status {status}")
        while True:
            if status.failed:
                log.error(f"k8s job {job_name} failed")
                raise Exception(f"k8s job {job_name} failed")
                break
            if status.succeeded:
                log.info(f"k8s job {job_name} succeeded")
                stdout = k8s.read_job_logs(
                    job_config["namespace"],
                    job_name,
                    context_name=job_config["context_name"],
                )
                break
            if not status.active:
                log.error(f"k8s job {job_name} stopped")
                raise Exception(
                    f"k8s job {job_name} not active (did not fail or succeed)"
                )
                break

            await asyncio.sleep(1)
            status = k8s.read_job_status(
                job_config["namespace"],
                job_name,
                context_name=job_config["context_name"],
            )
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


def scan_npm_package_then_build_report_tree(
    package_name: str, package_version: Optional[str] = None, **kwargs,
) -> None:
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

    # TODO: use asyncio.gather to run these concurrently
    fetch_and_save_registry_entries([package_name])

    fetch_and_save_npmsio_scores([package_name])

    scanned_package_name_and_versions: List[Tuple[str, str]] = []

    log.info(f"scanning {package_name}")

    # fetch npm registry entries from DB
    for (
        package_version,
        source_url,
        git_head,
        tarball_url,
    ) in models.get_npm_registry_entries_to_scan(package_name, package_version):
        if package_version is None:
            log.warn(f"skipping npm registry entry with null version {package_name}")
            continue

        log.info(f"scanning {package_name}@{package_version}")

        # we need a source_url and git_head or a tarball url to install
        if tarball_url:
            log.info(
                f"scanning {package_name}@{package_version} with {tarball_url} with config {current_app.config['SCAN_NPM_TARBALL_ARGS']}"
            )
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

            scanned_package_name_and_versions.append((package_name, package_version))
        elif source_url and git_head:
            # TODO: port scanner find_dep_files and run_repo_tasks pipelines as used in analyze_package.sh
            log.info(
                f"scanning {package_name}@{package_version} from {source_url}#{git_head} not implemented"
            )
            log.error(
                f"Installing from VCS source and ref not implemented to scan {package_name}@{package_version}"
            )

    # fetch missing registry entries and scores
    # TODO: use asyncio.gather to run these concurrently
    log.info(f"fetching missing npms.io scores")
    fetch_and_save_npmsio_scores(
        row[0]
        for row in models.get_package_names_with_missing_npms_io_scores()
        if row is not None
    )
    log.info(f"fetching missing npm registry entries")
    fetch_and_save_registry_entries(
        row[0]
        for row in models.get_package_names_with_missing_npm_entries()
        if row is not None
    )

    log.info(f"scoring package versions")
    for package_name, package_version in scanned_package_name_and_versions:
        log.info(f"scoring package version {package_name}@{package_version}")

        # build_report_tree(package_name, package_version)
        package: Optional[
            PackageVersion
        ] = get_most_recently_inserted_package_from_name_and_version(
            package_name, package_version
        )
        if package is None:
            log.error(
                f"PackageVersion not found for {package_name} {package_version}. Skipping scoring."
            )
            continue

        db_graph: Optional[PackageGraph] = get_latest_graph_including_package_as_parent(
            package
        )
        if db_graph is None:
            log.info(f"{package.name} {package.version} has no children")
            db_graph = PackageGraph(id=None, link_ids=[])
            db_graph.distinct_package_ids = set([package.id])

        store_package_reports(list(scoring.score_package_graph(db_graph).values()))


async def fetch_package_data(
    fetcher: Callable[
        [AIOHTTPClientConfig, Iterable[str], Optional[int]],
        AsyncGenerator[Result[Dict[str, Dict]], None],
    ],
    config: AIOHTTPClientConfig,
    package_names: List[str],
) -> List[Dict]:
    package_results = []
    # TODO: figure this type error out later
    async for package_result in fetcher(config, package_names, len(package_names)):  # type: ignore
        if isinstance(package_result, Exception):
            raise package_result
        package_results.append(package_result)

    return package_results


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
        log.warn(
            f"only fetched {len(npmsio_scores)} scores for {len(package_names)} package names"
        )
    else:
        log.info(
            f"fetched {len(npmsio_scores)} scores for {len(package_names)} package names"
        )
    if current_app.config["NPMSIO_CLIENT"].get("save_to_db", False):
        models.save_json_results(npmsio_scores)

    models.insert_npmsio_scores(
        serializers.serialize_npmsio_scores(
            score for score in npmsio_scores if score is not None
        )
    )
    return npmsio_scores


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
        log.warn(
            f"only fetched {len(npm_registry_entries)} registry entries for {len(package_names)} package names"
        )
    else:
        log.info(
            f"fetched {len(npm_registry_entries)} registry entries for {len(package_names)} package names"
        )
    if current_app.config["NPM_CLIENT"].get("save_to_db", False):
        models.save_json_results(npm_registry_entries)

    # inserts new entries for new versions (but doesn't update old ones)
    models.insert_npm_registry_entries(
        serializers.serialize_npm_registry_entries(
            registry_entry
            for registry_entry in npm_registry_entries
            if registry_entry is not None
        )
    )
    return npm_registry_entries


def get_github_advisories_for_package(package_name: str) -> None:

    github_client = current_app.config["GITHUB_CLIENT"]
    base_url = github_client["base_url"]
    github_auth_token = github_client["github_auth_token"]

    headers = {"Authorization": "token " + github_auth_token}

    query = f"""
    {{
        securityVulnerabilities(ecosystem: NPM, first: 100, package: \"{package_name}\", orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
            nodes {{
                advisory {{
                    id, description, permalink, publishedAt, severity, summary, updatedAt, withdrawnAt
                }}
                package {{
                    name
                }}
            }}
            pageInfo {{
                endCursor, hasNextPage, hasPreviousPage, startCursor
            }}
            totalCount
        }}
    }}
    """

    response = requests.post(base_url, json={"query": query}, headers=headers)
    response.raise_for_status()
    nodes = response.json()["data"]["securityVulnerabilities"]["nodes"]

    advisories = list()
    ids = list()
    for node in nodes:
        if (
            node["advisory"]["id"] not in ids
            and node["advisory"]["withdrawnAt"] == None
        ):
            advisory = node["advisory"]
            advisory["package"] = package_name
            advisories.append(advisory)
            ids.append(node["advisory"]["id"])

    save_json_results(advisories)


def get_github_advisories() -> None:

    github_client = current_app.config["GITHUB_CLIENT"]
    base_url = github_client["base_url"]
    github_auth_token = github_client["github_auth_token"]

    headers = {"Authorization": "token " + github_auth_token}

    perPage = 100

    query = f"""
    {{
        securityVulnerabilities(ecosystem: NPM, first: {perPage}, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
            nodes {{
                advisory {{
                    id, description, permalink, publishedAt, severity, summary, updatedAt, withdrawnAt
                }}
                package {{
                    name
                }}
            }}
            pageInfo {{
                endCursor, hasNextPage, hasPreviousPage, startCursor
            }}
            totalCount
        }}
    }}
    """

    response = requests.post(base_url, json={"query": query}, headers=headers)
    response.raise_for_status()
    response_json = response.json()["data"]["securityVulnerabilities"]

    nodes = response_json["nodes"]
    hasNextPage = response_json["pageInfo"]["hasNextPage"]
    endCursor = response_json["pageInfo"]["endCursor"]

    while hasNextPage:
        query = f"""
        {{
            securityVulnerabilities(ecosystem: NPM, first: {perPage}, after: \"{endCursor}\", orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
                nodes {{
                    advisory {{
                        id, description, permalink, publishedAt, severity, summary, updatedAt, withdrawnAt
                    }}
                    package {{
                        name
                    }}
                }}
                pageInfo {{
                    endCursor, hasNextPage, hasPreviousPage, startCursor
                }}
                totalCount
            }}
        }}
        """

        response = requests.post(base_url, json={"query": query}, headers=headers)
        response.raise_for_status()
        response_json = response.json()["data"]["securityVulnerabilities"]

        nodes += response_json["nodes"]
        hasNextPage = response_json["pageInfo"]["hasNextPage"]
        endCursor = response_json["pageInfo"]["endCursor"]

    advisories = list()
    ids = list()
    for node in nodes:
        if (
            node["advisory"]["id"] not in ids
            and node["advisory"]["withdrawnAt"] == None
        ):
            advisory = node["advisory"]
            advisories.append(advisory)
            ids.append(node["advisory"]["id"])

    save_json_results(advisories)


async def fetch_breach_data(
    fetcher: Callable[
        [AIOHTTPClientConfig, Iterable[str],],
        AsyncGenerator[Result[Dict[str, Dict]], None],
    ],
    config: AIOHTTPClientConfig,
    emails: List[str],
) -> List[Dict]:
    breach_results = []

    async for breach_result in fetcher(config, emails):
        if isinstance(breach_result, Exception):
            raise breach_result
        breach_results.append(breach_result)

    return breach_results


def get_maintainer_breaches(package_name: str, package_version: str = None) -> None:

    registry_entries = get_NPMRegistryEntry(package_name).all()

    if not registry_entries:
        return

    registry_entry = registry_entries[0]

    if package_version:

        package_version_validation_error = validators.get_npm_package_version_validation_error(
            package_version
        )
        if package_version_validation_error is not None:
            raise package_version_validation_error

        for entry in registry_entries:
            if entry.package_version == package_version:
                registry_entry = entry
                break

    maintainers = registry_entry.maintainers
    emails = [maintainer["email"] for maintainer in maintainers]

    breach_results = dict()
    total_breaches = 0

    if maintainers:

        breaches = fetch_breaches(emails)

        for email, breach_list in zip(emails, breaches):

            breach_results[email] = {
                "breach_num": len(breach_list),
                "breaches": breach_list,
            }
            total_breaches += len(breach_list)

    average_breaches = total_breaches / len(emails) if len(emails) else 0.0

    result = {
        "package_name": package_name,
        "package_version": package_version,
        "breaches": breach_results,
        "total_breaches": total_breaches,
        "average_breaches": average_breaches,
    }

    save_json_results([result])


def fetch_breaches(emails: List[str]) -> List[Dict[str, str]]:

    breaches = asyncio.run(
        fetch_breach_data(
            fetch_hibp_breach_data, current_app.config["HIBP_CLIENT"], emails,
        ),
        debug=False,
    )

    return breaches
