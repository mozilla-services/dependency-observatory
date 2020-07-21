import asyncio
import logging
from urllib import parse
from typing import Any, AsyncGenerator, Dict, Iterable, Optional

from depobs.clients.aiohttp_client import (
    AIOHTTPClientConfig,
    aiohttp_session,
    request_json,
)
from depobs.util.serialize_util import grouper
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
    async with aiohttp_session(config) as s:
        results = await asyncio.gather(
            *[
                request_json(
                    s,
                    "GET",
                    # f"{config['base_url']}breachedaccount/{parse.quote_plus(email)}",
                    f"{config['base_url']}breachedaccount/{email}",
                )
                for email in emails
            ]
        )

        for result in results:
            if result is None:
                log.warn(
                    f"got None HIBP results for emails {emails}"
                )
                continue
            yield result
