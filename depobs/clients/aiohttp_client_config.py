from typing import TypedDict


class AIOHTTPClientConfig(TypedDict, total=True):  # require keys defined below
    """
    Shared base AIOHTTPClient config.
    """

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
