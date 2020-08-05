import asyncio
import concurrent.futures
import copy
import functools
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
    Set,
    Tuple,
    TypedDict,
)

import flask
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
)
from depobs.util.type_util import Result
from depobs.worker import gcp
from depobs.worker import k8s

log = logging.getLogger(__name__)


class RunRepoTasksConfig(k8s.KubeJobConfig, total=True):
    # Language to run commands for
    language: str

    # Package manager to run commands for
    package_manager: str

    # Run install, list_metadata, or audit tasks in the order
    # provided
    repo_tasks: List[str]


async def scan_tarball_url(
    config: RunRepoTasksConfig,
    tarball_url: str,
    scan_id: int,
    package_name: str,
    package_version: Optional[str] = None,
) -> kubernetes.client.models.v1_job.V1Job:
    """
    Takes a run_repo_tasks config, tarball url, and optional package
    name and version.

    Returns the k8s job
    """
    job_name = config["name"]
    job_config: k8s.KubeJobConfig = {
        "backoff_limit": config["backoff_limit"],
        "ttl_seconds_after_finished": config["ttl_seconds_after_finished"],
        "context_name": config["context_name"],
        "name": config["name"],
        "namespace": config["namespace"],
        "image_name": config["image_name"],
        "args": config["repo_tasks"],
        "env": {
            **config["env"],
            "LANGUAGE": config["language"],
            "PACKAGE_MANAGER": config["package_manager"],
            "PACKAGE_NAME": package_name or "unknown-package-name",
            "PACKAGE_VERSION": package_version or "unknown-package-version",
            # see: https://github.com/mozilla-services/dependency-observatory/issues/280#issuecomment-641588717
            "INSTALL_TARGET": ".",
            "JOB_NAME": config["name"],
            "SCAN_ID": str(scan_id),
        },
        "secrets": config["secrets"],
        "service_account_name": config["service_account_name"],
        "volume_mounts": config["volume_mounts"],
    }
    log.info(f"scan {scan_id} starting job {job_name} with config {job_config}")
    status = None
    with k8s.run_job(job_config) as job:
        log.info(f"scan {scan_id} started job {job}")
        await asyncio.sleep(1)
        job = k8s.read_job(
            job_config["namespace"], job_name, context_name=job_config["context_name"]
        )
        log.info(f"scan {scan_id} got initial job status {job.status}")
        while True:
            if job.status.failed:
                log.error(f"scan {scan_id} k8s job {job_name} failed")
                return job
            if job.status.succeeded:
                log.info(f"scan {scan_id} k8s job {job_name} succeeded")
                return job
            if not job.status.active:
                log.error(
                    f"scan {scan_id} k8s job {job_name} stopped/not active (did not fail or succeed)"
                )
                return job

            await asyncio.sleep(5)
            job = k8s.read_job(
                job_config["namespace"],
                job_name,
                context_name=job_config["context_name"],
            )
            log.info(f"scan {scan_id} got job status {job.status}")


def scan_package_tarballs(scan: models.Scan) -> Generator[asyncio.Task, None, None]:
    """Given a scan, uses its package name and optional version params, checks for matching npm
    registry entries and start k8s jobs to scan the tarball url for
    each version.

    Generates scan jobs with format asyncio.Task that terminate when
    the k8s finishes.

    When the version is 'latest' only scans the most recently published version of the package.
    """
    package_name: str = scan.package_name
    package_version: Optional[str] = scan.package_version
    if package_version == "latest":
        versions_query = models.get_npm_registry_entries_to_scan(
            package_name, None
        ).limit(1)
    else:
        versions_query = models.get_npm_registry_entries_to_scan(
            package_name, package_version
        )

    # fetch npm registry entries from DB
    for (package_version, source_url, git_head, tarball_url,) in versions_query:
        if package_version is None:
            log.warn(
                f"scan: {scan.id} skipping npm registry entry with null version {package_name}"
            )
            continue
        elif not validators.is_npm_release_package_version(package_version):
            log.warn(
                f"scan: {scan.id} {package_name} skipping npm registry entry with pre-release version {package_version!r}"
            )
            continue

        log.info(f"scan: {scan.id} scanning {package_name}@{package_version}")
        # we need a source_url and git_head or a tarball url to install
        if tarball_url:
            job_name = f"scan-tarball-url-{hex(randrange(1 << 32))[2:]}"
            config: RunRepoTasksConfig = copy.deepcopy(
                current_app.config["SCAN_NPM_TARBALL_ARGS"]
            )
            config["name"] = job_name

            log.info(
                f"scan: {scan.id} scanning {package_name}@{package_version} with {tarball_url} with config {config}"
            )
            # start an npm container, install the tarball, run list and audit
            # assert tarball_url == f"https://registry.npmjs.org/{package_name}/-/{package_name}-{package_version}.tgz
            yield asyncio.create_task(
                scan_tarball_url(
                    config, tarball_url, scan.id, package_name, package_version
                ),
                name=job_name,
            )
        elif source_url and git_head:
            # TODO: port scanner find_dep_files and run_repo_tasks pipelines as used in analyze_package.sh
            log.info(
                f"scan: {scan.id} scanning {package_name}@{package_version} from {source_url}#{git_head} not implemented"
            )
            log.error(
                f"scan: {scan.id} Installing from VCS source and ref not implemented to scan {package_name}@{package_version}"
            )


async def scan_score_npm_package(scan: models.Scan) -> None:
    """
    Scan and score an npm package using params from the provided Scan model
    """
    package_name: str = scan.package_name
    package_version: Optional[str] = scan.package_version
    log.info(
        f"scan: {scan.id} fetching npms.io score and npm registry entry for {package_name}"
    )
    await asyncio.gather(
        fetch_and_save_registry_entries([package_name]),
        fetch_and_save_npmsio_scores([package_name]),
    )

    tarball_scans: List[asyncio.Task] = list(scan_package_tarballs(scan))
    log.info(f"scan: {scan.id} scanning {package_name} {len(tarball_scans)} versions")
    k8s_jobs: List[kubernetes.client.models.v1_job.V1Job] = await asyncio.gather(
        *tarball_scans
    )
    successful_jobs = [job for job in k8s_jobs if job.status.succeeded]
    log.info(
        f"scan: {scan.id} {len(k8s_jobs)} k8s jobs finished, {len(successful_jobs)}) succeeded"
    )

    # wait for logs to show up from pubsub
    successful_job_names = {
        k8s.get_job_env_var(job, "JOB_NAME") for job in successful_jobs
    }
    while True:
        jobs_completed = {
            job_name: any(
                result.data["data"][-1]["type"] == "task_complete"
                for result in models.get_scan_job_results(job_name)
            )
            for job_name in successful_job_names
        }
        log.info(
            f"scan: {scan.id} {jobs_completed.keys()} finished; waiting for pubsub logs from {successful_job_names - set(jobs_completed.keys())}"
        )
        if set(jobs_completed.keys()) == successful_job_names:
            break
        await asyncio.sleep(5)

    log.info(f"scan: {scan.id} saving logs from {len(successful_jobs)} successful jobs")
    for job in successful_jobs:
        log.info(
            f"scan: {scan.id} saving job results for {k8s.get_job_env_var(job, 'PACKAGE_NAME')}@{k8s.get_job_env_var(job, 'PACKAGE_VERSION')}"
        )
        serializers.deserialize_scan_job_results(
            models.get_scan_job_results(k8s.get_job_env_var(job, "JOB_NAME"))
        )

    log.info(
        f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
    )
    await asyncio.gather(
        fetch_and_save_npmsio_scores(
            row[0]
            for row in models.get_package_names_with_missing_npms_io_scores()
            if row is not None
        ),
        fetch_and_save_registry_entries(
            row[0]
            for row in models.get_package_names_with_missing_npm_entries()
            if row is not None
        ),
    )

    log.info(f"scan: {scan.id} scoring {len(successful_jobs)} package versions")
    for job in successful_jobs:
        package_name, package_version = (
            k8s.get_job_env_var(job, "PACKAGE_NAME"),
            k8s.get_job_env_var(job, "PACKAGE_VERSION"),
        )
        log.info(
            f"scan: {scan.id} scoring package version {package_name}@{package_version}"
        )

        package: Optional[
            PackageVersion
        ] = get_most_recently_inserted_package_from_name_and_version(
            package_name, package_version
        )
        if package is None:
            log.error(
                f"scan: {scan.id} PackageVersion not found for {package_name} {package_version}. Skipping scoring."
            )
            continue

        db_graph: Optional[PackageGraph] = get_latest_graph_including_package_as_parent(
            package
        )
        if db_graph is None:
            log.info(
                f"scan: {scan.id} {package.name} {package.version} has no children"
            )
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


async def fetch_and_save_npmsio_scores(package_names: Iterable[str]) -> List[Dict]:
    package_names = list(package_names)
    log.info(f"fetching npmsio scores for {len(package_names)} package names")
    log.debug(f"fetching npmsio scores for package names: {list(package_names)}")
    npmsio_scores: List[Dict] = await asyncio.create_task(
        fetch_package_data(
            fetch_npmsio_scores, current_app.config["NPMSIO_CLIENT"], package_names,
        ),
        name=f"fetch_npmsio_scores",
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


async def fetch_and_save_registry_entries(package_names: Iterable[str]) -> List[Dict]:
    package_names = list(package_names)
    log.info(f"fetching registry entries for {len(package_names)} package names")
    log.debug(f"fetching registry entries for package names: {list(package_names)}")
    npm_registry_entries = await asyncio.create_task(
        fetch_package_data(
            fetch_npm_registry_metadata,
            current_app.config["NPM_CLIENT"],
            package_names,
        ),
        name=f"fetch_and_save_registry_entries",
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


def save_pubsub_message(
    app: flask.Flask, message: gcp.pubsub_v1.types.PubsubMessage
) -> None:
    """
    Saves a pubsub message data to the JSONResult table and acks it.

    nacks it if saving fails.

    Requires depobs flask app context.
    """
    with app.app_context():
        try:
            # TODO: set job status when it finishes? No, do this in the runner.
            log.info(
                f"received pubsub message {message.message_id} published at {message.publish_time} with attrs {message.attributes}"
            )
            save_json_results(
                [
                    {
                        "type": "google.cloud.pubsub_v1.types.PubsubMessage",
                        "id": message.message_id,
                        "publish_time": flask.json.dumps(
                            message.publish_time
                        ),  # convert datetime
                        "attributes": dict(
                            message.attributes
                        ),  # convert from ScalarMapContainer
                        "data": flask.json.loads(message.data),
                        "size": message.size,
                    }
                ]
            )
            message.ack()
        except Exception as err:
            message.nack()
            log.error(
                f"error saving pubsub message {message} to json results table: {err}"
            )


def run_pubsub_thread(app: flask.Flask, timeout=30):
    """
    Runs a thread that:

    * subscribes to GCP pubsub output
    * saves the job output to the JSONResult table

    Requires depobs flask app context.
    """
    with app.app_context():
        future: gcp.pubsub_v1.subscriber.futures.StreamingPullFuture = gcp.receive_pubsub_messages(
            current_app.config["GCP_PROJECT_ID"],
            current_app.config["JOB_STATUS_PUBSUB_TOPIC"],
            current_app.config["JOB_STATUS_PUBSUB_SUBSCRIPTION"],
            functools.partial(save_pubsub_message, app),
        )
        while True:
            try:
                future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                log.debug(f"{timeout}s timeout for pubsub receiving exceeded")
            except KeyboardInterrupt:  # stop the thread on keyboard interrupt
                future.cancel()


async def save_pubsub(app: flask.Flask) -> None:
    loop = asyncio.get_running_loop()

    # run in the default loop executor
    await loop.run_in_executor(None, functools.partial(run_pubsub_thread, app))


async def run_next_scan(app: flask.Flask) -> Optional[models.Scan]:
    """
    Async task that:

    * fetches the next scan job (returns None when one isn't found)

    Returns the updated scan or None (when one isn't found to run).
    """
    # try to read the next queued scan from the scans table if we weren't given one
    log.debug("checking for a scan in the DB to run")
    maybe_next_scan: Optional[models.Scan] = models.get_next_queued_scan().one_or_none()
    if maybe_next_scan is None:
        log.debug("could not find a scan in the DB to run")
        await asyncio.sleep(5)
        return None
    return await run_scan(app, maybe_next_scan)


async def run_scan(app: flask.Flask, scan: models.Scan,) -> models.Scan:
    """
    Async task that:

    * takes a scan job
    * starts a k8s job in the untrusted jobs cluster
    * updates the scan status from 'queued' to 'started'
    * watches the k8s job and sets the scan status to 'failed' or 'succeeded' when the k8s job finishes

    Returns the updated scan.
    """
    log.info(f"starting a k8s job for scan {scan.id} with params {scan.params}")
    if (
        isinstance(scan.params, dict)
        and all(k in scan.params.keys() for k in {"name", "args", "kwargs"})
        and scan.params["name"] == "scan_score_npm_package"
    ):
        args = scan.params["args"]
        package_name = args[0]
        package_version = args[1] if len(args) > 1 else None

        with app.app_context():
            scan = models.save_scan_with_status(scan, "started")
            # scan fails if any of its tarball scan jobs, data fetching, or scoring steps fail
            try:
                await scan_score_npm_package(scan)
                new_scan_status = "succeeded"
            except Exception as err:
                log.error(f"{scan.id} error scanning and scoring: {err}")
                new_scan_status = "failed"
            scan = models.save_scan_with_status(scan, new_scan_status)
    else:
        log.info("ignoring pending scan {scan.id} with params {scan.params}")

    return scan


async def run_background_tasks(app: flask.Flask, task_fns: Iterable[Callable]) -> None:
    """
    Repeatedly runs one or more tasks with the param task_name until
    the shutdown event fires.
    """
    shutdown = asyncio.Event()

    task_fns_by_name = {
        task_fn.__name__: functools.partial(task_fn, app) for task_fn in task_fns
    }
    tasks: Set[asyncio.Task] = {
        asyncio.create_task(fn(), name=name) for name, fn in task_fns_by_name.items()
    }
    log.info(f"starting initial background tasks {tasks}")
    while True:
        done, pending = await asyncio.wait(
            tasks, timeout=5, return_when=asyncio.FIRST_COMPLETED
        )
        assert all(isinstance(task, asyncio.Task) for task in pending)
        log.debug(
            f"background task {done} completed, running: {[task.get_name() for task in pending]}"  # type: ignore
        )
        if shutdown.is_set():
            # wait for everything to finish
            await asyncio.wait(pending, return_when=asyncio.ALL_COMPLETED)
            log.info("all background tasks finished exiting")
            break

        for task in tasks:
            if task.done():
                if task.cancelled():
                    log.warn(f"task {task.get_name()} was cancelled")
                elif task.exception():
                    log.error(f"task {task.get_name()} errored")
                    task.print_stack()
                elif task.result() is None:
                    log.debug(f"task {task.get_name()} finished with result: None")
                else:
                    log.info(
                        f"task {task.get_name()} finished with result: {task.result()}"
                    )
                log.debug(f"queuing a new {task.get_name()} task")
                tasks.remove(task)
                tasks.add(
                    asyncio.create_task(
                        task_fns_by_name[task.get_name()](), name=task.get_name()
                    )
                )
