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
from depobs.clients.hibp import fetch_hibp_breach_data
from depobs.database.models import (
    get_NPMRegistryEntry,
    save_json_results,
)
from depobs.util.type_util import Result
import depobs.worker.validators as validators


log = logging.getLogger(__name__)


def get_maintainer_breaches(package_name: str, package_version: str = None) -> None:

    registry_entries = get_NPMRegistryEntry(package_name).all()

    if not registry_entries:
        return

    registry_entry = registry_entries[0]

    if package_version:

        package_version_validation_error = (
            validators.get_npm_package_version_validation_error(package_version)
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
            fetch_hibp_breach_data,
            current_app.config["HIBP_CLIENT"],
            emails,
        ),
        debug=False,
    )
    return breaches


async def fetch_breach_data(
    fetcher: Callable[
        [
            AIOHTTPClientConfig,
            Iterable[str],
        ],
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
