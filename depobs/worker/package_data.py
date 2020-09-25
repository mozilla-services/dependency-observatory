import asyncio
import logging
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
    Union,
)

from flask import current_app

from depobs.clients.aiohttp_client import AIOHTTPClientConfig, is_not_found_exception
from depobs.clients.npmsio import fetch_npmsio_scores
from depobs.clients.npm_registry import fetch_npm_registry_metadata
import depobs.database.models as models
from depobs.util.type_util import Result
import depobs.worker.serializers as serializers


log = logging.getLogger(__name__)


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
            if is_not_found_exception(package_result):
                continue
            raise package_result
        package_results.append(package_result)

    return package_results


async def fetch_and_save_npmsio_scores(package_names: Iterable[str]) -> List[Dict]:
    package_names = list(package_names)
    log.info(f"fetching npmsio scores for {len(package_names)} package names")
    log.debug(f"fetching npmsio scores for package names: {list(package_names)}")
    npmsio_scores: List[Dict] = await asyncio.create_task(
        fetch_package_data(
            fetch_npmsio_scores,
            current_app.config["NPMSIO_CLIENT"],
            package_names,
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


async def fetch_missing_npm_data():
    await asyncio.gather(
        fetch_and_save_npmsio_scores(
            row[0]
            for row in models.get_package_names_with_missing_npmsio_scores()
            if row is not None
        ),
        fetch_and_save_registry_entries(
            row[0]
            for row in models.get_package_names_with_missing_npm_entries()
            if row is not None
        ),
    )
