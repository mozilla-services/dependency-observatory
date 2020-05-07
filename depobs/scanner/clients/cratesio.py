import asyncio
import logging
from typing import AbstractSet, Dict, AsyncGenerator, Generator, Optional

import aiohttp

from depobs.scanner.clients.aiohttp_client_config import AIOHTTPClientConfig
from depobs.scanner.models.rust import (
    RustPackageID,
    cargo_metadata_to_rust_crates,
)
from depobs.scanner.models.package_meta_result import Result


log = logging.getLogger(__name__)


class CratesIOClientConfig(
    AIOHTTPClientConfig, total=False
):  # don't require keys defined below
    pass


__doc__ = """Given cargo metadata output fetches metadata from the crates.io
registry for the resolved packages and outputs them as jsonlines.

Assumes all crates with non-file source are on crates.io and reads all cargo
metadata into memory.
"""


def aiohttp_session(config: CratesIOClientConfig) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": config["user_agent"],
        },
        timeout=aiohttp.ClientTimeout(total=config["total_timeout"]),
        connector=aiohttp.TCPConnector(limit=config["max_connections"]),
        raise_for_status=True,
    )


async def async_query(
    config: CratesIOClientConfig, session: aiohttp.ClientSession, url: str
) -> Result[Optional[Dict]]:
    await asyncio.sleep(config["delay"])
    try:
        log.debug(f"fetching crates-io-metadata for {url}")
        async with session.get(url) as resp:
            response_json = await resp.json()
    except Exception as err:
        return err

    return response_json


async def fetch_cratesio_metadata(
    config: CratesIOClientConfig, source: Generator[Dict, None, None]
) -> AsyncGenerator[Dict, None]:
    log.info("pipeline crates_io_metadata started")
    rust_crate_ids: Generator[RustPackageID, None, None] = (
        rust_crate.package_id
        for cargo_meta in source
        for rust_crate in cargo_metadata_to_rust_crates(cargo_meta).values()
    )

    async with aiohttp_session(config) as session:
        for rust_crate_id in rust_crate_ids:
            url = rust_crate_id.crates_io_metadata_url
            if url is None:
                log.info(f"skipping crate {rust_crate_id} with non-registry source")

        urls: AbstractSet[str] = set(
            [
                rust_crate_id.crates_io_metadata_url
                for rust_crate_id in rust_crate_ids
                if rust_crate_id.crates_io_metadata_url is not None
            ]
        )
        results = await asyncio.gather(
            *[async_query(config, session, url) for url in urls]
        )
        for result in results:
            if result is not None:
                yield result
