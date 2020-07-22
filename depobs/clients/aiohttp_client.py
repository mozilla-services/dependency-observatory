import logging
from typing import Any, Dict, TypedDict, Optional

import aiohttp

from depobs.util.type_util import Result


log = logging.getLogger(__name__)


class AIOHTTPClientConfig(TypedDict, total=True):  # require all keys defined below
    """
    Shared base AIOHTTPClient config.
    """

    # scheme, host, port, and any base URI prefix
    # should end with a slash
    # should not include basic auth/userinfo
    base_url: str

    # time to sleep between requests in seconds
    delay: int

    # number of simultaneous connections to open
    max_connections: int

    # number of times to retry requests
    max_retries: int

    # number of packages to fetch in once request (for APIs that support it)
    package_batch_size: int

    # aiohttp total timeout in seconds
    total_timeout: int

    # User agent to use to query third party APIs
    user_agent: str

    # optional API token
    bearer_auth_token: Optional[str]

    # optional additional headers
    additional_headers: Optional[Dict[str, str]]


def aiohttp_session(config: AIOHTTPClientConfig) -> aiohttp.ClientSession:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": config["user_agent"],
    }
    if config.get("bearer_auth_token", None):
        headers["Authorization"] = f"Bearer {config['bearer_auth_token']}"
    if config.get("additional_headers", None):
        additional_headers = config["additional_headers"]
        for header in additional_headers:
            headers[header] = additional_headers[header]

    return aiohttp.ClientSession(
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=config["total_timeout"]),
        connector=aiohttp.TCPConnector(limit=config["max_connections"]),
        raise_for_status=True,
    )


def is_not_found_exception(err: Exception) -> bool:
    is_aiohttp_404 = isinstance(err, aiohttp.ClientResponseError) and err.status == 404
    return is_aiohttp_404


async def request_json(
    session: aiohttp.ClientSession, method: str, url: str, **kwargs: Any
) -> Result[Dict]:
    log.debug(f"{method} {url}")
    try:
        response = await session.request(method, url, **kwargs)
        response_json = await response.json()
    except Exception as err:
        if is_not_found_exception(err):
            log.info(f"got 404 for {url}")
            log.debug(f"{url} not found: {err}")
            return err
        raise err
    log.debug(f"got response json {response_json!r}")
    return response_json
