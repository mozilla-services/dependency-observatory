import asyncio
import contextlib
import sys
import os
import logging
import json
import shlex
from typing import (
    Any,
    AsyncGenerator,
    BinaryIO,
    IO,
    Sequence,
    List,
    Generator,
    Union,
    Dict,
    Optional,
    Tuple,
)
import aiodocker

from depobs.docker.client import aiodocker_client
import depobs.docker.log_reader as docker_log_reader
from depobs.util.traceback_util import exc_to_str

log = logging.getLogger(__name__)


# https://docs.docker.com/engine/api/v1.37/#operation/ExecInspect
# {
#   "CanRemove": false,
#   "ContainerID": "b53ee82b53a40c7dca428523e34f741f3abc51d9f297a14ff874bf761b995126",
#   "DetachKeys": "",
#   "ExitCode": 2,
#   "ID": "f33bbfb39f5b142420f4759b2348913bd4a8d1a6d7fd56499cb41a1bb91d7b3b",
#   "OpenStderr": true,
#   "OpenStdin": true,
#   "OpenStdout": true,
#   "ProcessConfig": {
#     "arguments": [
#       "-c",
#       "exit 2"
#     ],
#     "entrypoint": "sh",
#     "privileged": false,
#     "tty": true,
#     "user": "1000"
#   },
#   "Running": false,
#   "Pid": 42000
# }
DockerExecInspectResult = Dict[str, Union[int, str, List[str], bool]]


class DockerRunException(Exception):
    pass


class Exec:
    # from: https://github.com/hirokiky/aiodocker/blob/8a91b27cff7311398ca36f5453d94679fed99d11/aiodocker/execute.py

    def __init__(self, exec_id: str, container: aiodocker.docker.DockerContainer):
        self.exec_id: str = exec_id
        self.container: aiodocker.docker.DockerContainer = container
        self.start_result: Optional[bytes] = None

    @classmethod
    async def create(
        cls, container: aiodocker.docker.DockerContainer, **kwargs
    ) -> "Exec":
        """ Create and return an instance of Exec
        """
        log.debug(f"execing with config {kwargs}")
        data = await container.docker._query_json(
            f"containers/{container._id}/exec", method="POST", data=kwargs
        )
        return cls(data["Id"], container)

    async def start(self: "Exec", timeout: int = None, **kwargs) -> bytes:
        """
        Start executing a process

        returns result of exec process as binary string.
        """
        # Don't use docker._query_json
        # content-type of response will be "vnd.docker.raw-stream",
        # so it will cause error.
        response_cm = self.container.docker._query(
            f"exec/{self.exec_id}/start",
            method="POST",
            headers={"content-type": "application/json"},
            data=json.dumps(kwargs),
            timeout=timeout,
        )
        async with response_cm as response:
            result = await response.read()
            response.release()
            return result

    async def resize(self: "Exec", **kwargs) -> None:
        await self.container.docker._query(
            f"exec/{self.exec_id}/resize", method="POST", params=kwargs
        )

    async def inspect(self: "Exec") -> DockerExecInspectResult:
        data = await self.container.docker._query_json(
            f"exec/{self.exec_id}/json", method="GET"
        )
        return data

    async def wait(self: "Exec") -> None:
        while True:
            resp = await self.inspect()
            log.debug("Exec wait resp:", resp)
            if resp["Running"] is False:
                break
            else:
                await asyncio.sleep(0.1)

    @property
    def decoded_start_result_stdout_and_stderr_line_iters(
        self: "Exec",
    ) -> Tuple[Generator[str, None, None], Generator[str, None, None]]:
        assert self.start_result is not None
        return docker_log_reader.stdout_stderr_line_iters(
            docker_log_reader.iter_messages(self.start_result)
        )

    @property
    def decoded_start_result_stdout(self: "Exec") -> List[str]:
        assert self.start_result is not None
        return list(
            docker_log_reader.iter_lines(
                docker_log_reader.iter_messages(self.start_result),
                output_stream=docker_log_reader.DockerLogStream.STDOUT,
            )
        )


async def _exec_create(self: aiodocker.containers.DockerContainer, **kwargs) -> Exec:
    """ Create an exec (Instance of Exec).
    """
    return await Exec.create(self, **kwargs)


aiodocker.containers.DockerContainer.exec_create = _exec_create


async def _run(
    self: aiodocker.containers.DockerContainer,
    cmd: str,
    attach_stdout: bool = True,
    attach_stderr: bool = True,
    detach: bool = False,
    tty: bool = False,
    working_dir: Optional[str] = None,
    # fpr specific args
    wait: bool = True,
    check: bool = True,
    **kwargs,
) -> Exec:
    """Create and run an instance of exec (Instance of Exec). Optionally wait for it to finish and check its exit code
    """
    config = dict(
        Cmd=shlex.split(cmd),
        AttachStdout=attach_stdout,
        AttachStderr=attach_stderr,
        Tty=tty,
    )
    if working_dir is not None:
        config["WorkingDir"] = working_dir
    container_log_name = self["Name"] if "Name" in self._container else self["Id"]
    log.debug(f"container {container_log_name} in {working_dir} running {cmd!r}")
    exec_ = await self.exec_create(**config)
    exec_.start_result = await exec_.start(Detach=detach, Tty=tty)

    if wait:
        await exec_.wait()
    if check:
        last_inspect = await exec_.inspect()
        if last_inspect["ExitCode"] != 0:
            stdout, stderr = [
                "\n".join(line_iter)
                for line_iter in exec_.decoded_start_result_stdout_and_stderr_line_iters
            ]
            log.info(
                f"{self._id} command {cmd!r} failed with:\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
            raise DockerRunException(
                f"{self._id} command {cmd} failed with non-zero exit code {last_inspect['ExitCode']}"
            )
    return exec_


aiodocker.containers.DockerContainer.run = _run


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
