import asyncio
import logging
from typing import AsyncGenerator, Dict, Iterable, Optional

from depobs.clients.aiohttp_client import (
    AIOHTTPClientConfig,
    aiohttp_session,
    request_json,
)
from depobs.util.serialize_util import grouper
from depobs.util.type_util import Result

log = logging.getLogger(__name__)


async def fetch_npmsio_scores(
    config: AIOHTTPClientConfig,
    package_names: Iterable[str],
    total_packages: Optional[int] = None,
) -> AsyncGenerator[Result[Dict[str, Dict]], None]:
    """
    Fetches npms.io score and analysis for one or more node package names

    Uses: https://api-docs.npms.io/#api-Package-GetMultiPackageInfo
    """
    async with aiohttp_session(config) as s:
        group_results = await asyncio.gather(
            *[
                request_json(
                    s,
                    "POST",
                    f"{config['base_url']}package/mget",
                    json=[
                        package_name
                        for package_name in group
                        if package_name is not None
                    ],
                )
                for group in grouper(package_names, config["package_batch_size"])
                if group is not None
            ]
        )
        # NB: org/scope e.g. "@babel" in @babel/babel is flattened into the scope field.
        # pull {data1}, {data2} from {package_name_1: {data1}, package_name_2: {data2}}
        for group_result in group_results:
            if group_result is None:
                log.warn(f"got None npms.io group for package_names {package_names}")
                continue

            for result in group_result.values():
                if result is None:
                    log.warn(
                        f"got None npms.io results for package_names {package_names}"
                    )
                    continue
                yield result
