import contextlib
from typing import AsyncGenerator

import aiodocker


@contextlib.asynccontextmanager
async def aiodocker_client() -> AsyncGenerator[aiodocker.docker.Docker, None]:
    client = aiodocker.Docker()
    try:
        yield client
    finally:
        await client.close()
