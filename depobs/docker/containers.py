import contextlib
import logging
from typing import (
    Any,
    AsyncGenerator,
    List,
    Dict,
    Optional,
)
import aiodocker

from depobs.docker.client import aiodocker_client
from depobs.util.traceback_util import exc_to_str

log = logging.getLogger(__name__)


class DockerRunException(Exception):
    pass


@contextlib.asynccontextmanager
async def run(
    repository_tag: str,
    name: str,
    cmd: str = None,
    entrypoint: Optional[str] = None,
    working_dir: Optional[str] = None,
    env: Optional[List[str]] = None,
) -> AsyncGenerator[aiodocker.docker.DockerContainer, None]:
    async with aiodocker_client() as client:
        config: Dict[str, Any] = dict(
            Cmd=cmd,
            Image=repository_tag,
            LogConfig={"Type": "json-file"},
            AttachStdout=True,
            AttachStderr=True,
            Tty=True,
            HostConfig={
                # "ContainerIDFile": "./"
                "Mounts": []
            },
        )
        if entrypoint:
            config["Entrypoint"] = entrypoint
        if env:
            config["Env"] = env
        if working_dir:
            config["WorkingDir"] = working_dir
        log.info(f"starting image {repository_tag} as {name}")
        log.debug(f"container {name} starting {cmd} with config {config}")
        container = await client.containers.run(config=config, name=name)
        # fetch container info so we can include container name in logs
        await container.show()
        try:
            yield container
        except DockerRunException as e:
            container_log_name = (
                container["Name"] if "Name" in container._container else container["Id"]
            )
            log.error(
                f"{container_log_name} error running docker command {cmd}:\n{exc_to_str()}"
            )
        finally:
            await container.stop()
            await container.delete()
