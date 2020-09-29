import asyncio

import aiohttp
import backoff
import logging
from typing import AsyncGenerator, Dict, Iterable

from depobs.clients.aiohttp_client import (
    AIOHTTPClientConfig,
    aiohttp_session,
    is_not_found_exception,
    request_json,
)
from depobs.util.type_util import Result

log = logging.getLogger(__name__)


async def fetch_hibp_breach_data(
    config: AIOHTTPClientConfig,
    emails: Iterable[str],
) -> AsyncGenerator[Result[Dict[str, Dict]], None]:
    """
    Fetches breach information for one or more email accounts

    Uses: https://haveibeenpwned.com/API/v3#BreachesForAccount
    """

    async_query_with_backoff = backoff.on_exception(
        backoff.constant,
        (aiohttp.ClientResponseError, aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=config["max_retries"],
        giveup=is_not_found_exception,
        logger=log,
        interval=2,
    )(request_json)

    async with aiohttp_session(config) as s:
        results = await asyncio.gather(
            *[
                async_query_with_backoff(
                    s,
                    "GET",
                    f"{config['base_url']}breachedaccount/{email}",
                )
                for email in emails
            ]
        )

        for result in results:
            if result is None:
                log.warn(f"got None HIBP results for emails {emails}")
                continue

            breach_details = await asyncio.gather(
                *[
                    async_query_with_backoff(
                        s,
                        "GET",
                        f"{config['base_url']}breach/{breach['Name']}",
                    )
                    for breach in result
                ]
            )

            breach_dates = [detail["BreachDate"] for detail in breach_details]

            for dict, date in zip(result, breach_dates):
                dict["Date"] = date

            yield result
