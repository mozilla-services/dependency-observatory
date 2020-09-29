import asyncio

import aiohttp
import backoff
import math
from typing import AsyncGenerator, Dict, Iterable, Optional
import logging

from depobs.clients.aiohttp_client import (
    AIOHTTPClientConfig,
    aiohttp_session,
    is_not_found_exception,
    request_json,
)
from depobs.util.type_util import Result
from depobs.util.serialize_util import grouper
from depobs.util.traceback_util import exc_to_str

log = logging.getLogger(__name__)

"""
client providing one function to fetch_npm_registry_metadata

Notes:

"Accept": "application/json vnd.npm.install-v1+json; q=1.0, # application/json; q=0.8, */*"
doesn't include author and maintainer info

alternatively npm login then
npm view [<@scope>/]<name>[@<version>] [<field>[.<subfield>]...]

the registry does support GET /{package}/{version}

https://github.com/npm/registry/blob/master/docs/REGISTRY-API.md#getpackageversion

but it seems to be busted for scoped packages e.g.
e.g. https://registry.npmjs.com/@hapi/bounce/2.0.8

https://replicate.npmjs.com/ (flattened scopes) seems to be busted

"""


async def fetch_npm_registry_metadata(
    config: AIOHTTPClientConfig,
    package_names: Iterable[str],
    total_packages: Optional[int] = None,
) -> AsyncGenerator[Result[Dict[str, Dict]], None]:
    """Fetches npm registry metadata for one or more node package names

    config['auth_token'] is an optional npm registry access token to
    use a higher rate limit. Run 'npm token create --read-only' to
    create it.
    """
    total_groups: Optional[int] = None
    if total_packages:
        total_groups = math.ceil(total_packages / config["package_batch_size"])

    async with aiohttp_session(config) as s:
        async_query_with_backoff = backoff.on_exception(
            backoff.expo,
            (
                aiohttp.ClientError,
                aiohttp.ClientResponseError,
                aiohttp.ContentTypeError,
                asyncio.TimeoutError,
            ),
            max_tries=config["max_retries"],
            giveup=is_not_found_exception,
            logger=log,
        )(request_json)

        for i, group in enumerate(grouper(package_names, config["package_batch_size"])):
            log.info(f"fetching group {i} of {total_groups}")
            try:
                # NB: scoped packages OK e.g. https://registry.npmjs.com/@babel/core
                group_results = await asyncio.gather(
                    *[
                        async_query_with_backoff(
                            s,
                            "GET",
                            f"{config['base_url']}{package_name}",
                        )
                        for package_name in group
                        if package_name is not None
                    ]
                )
                for result in group_results:
                    if result is not None:
                        yield result
            except Exception as err:
                log.error(
                    f"error fetching group {i} for package names {group}: {err}:\n{exc_to_str()}"
                )
                yield err
