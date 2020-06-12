from typing import TypedDict, Optional

import aiohttp


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

    # don't hit the third part API just print intended actions
    dry_run: bool

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


def aiohttp_session(config: AIOHTTPClientConfig) -> aiohttp.ClientSession:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": config["user_agent"],
    }
    if config.get("bearer_auth_token", None):
        headers["Authorization"] = f"Bearer {config['bearer_auth_token']}"

    return aiohttp.ClientSession(
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=config["total_timeout"]),
        connector=aiohttp.TCPConnector(limit=config["max_connections"]),
        raise_for_status=True,
    )
