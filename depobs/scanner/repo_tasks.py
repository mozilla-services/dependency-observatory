import aiodocker
import asyncio
from collections import ChainMap
import itertools
import logging
from random import randrange
from typing import (
    AbstractSet,
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Tuple,
    TypedDict,
    Union,
)

import depobs.docker.containers as containers
from depobs.scanner.models.language import (
    ContainerTask,
    DependencyFile,
    DockerImage,
    Language,
    PackageManager,
    docker_images,
    docker_image_names,
    language_names,
    languages,
    package_manager_names,
    package_managers,
)

log = logging.getLogger(__name__)

__doc__ = """Runs tasks on a checked out git ref with dep. files"""


class RunRepoTasksConfig(TypedDict):
    # Print commands we would run and their context, but don't run them.
    dry_run: bool

    # Languages to run commands for. Defaults to all of them.
    # choices=language_names
    languages: List[str]

    # Package managers to run commands for. Defaults to all of them.
    # choices=package_manager_names,
    package_managers: List[str]

    # Docker images to run commands in. Defaults to all of them.
    # choices=docker_image_names,
    docker_images: List[str]

    # Run install, list_metadata, or audit tasks in the order
    # provided. Defaults to none of them
    repo_tasks: List[str]


async def run_repo_task(
    c: aiodocker.containers.DockerContainer,
    task: ContainerTask,
    working_dir: str,
    container_name: str,
) -> Union[Dict[str, Any], Exception]:
    last_inspect = dict(ExitCode=None)
    stdout = "dummy-stdout"

    log.info(
        f"task {task.name} running {task.command} in {working_dir} of {container_name}"
    )
    try:
        job_run = await c.run(
            cmd=task.command,
            working_dir=working_dir,
            wait=True,
            check=task.check,
            attach_stdout=task.attach_stdout,
            attach_stderr=task.attach_stderr,
            tty=task.tty,
        )
        last_inspect = await job_run.inspect()
    except containers.DockerRunException as e:
        log.error(
            f"{container_name} in {working_dir} for task {task.name} error running {task.command}: {e}"
        )
        return e

    stdout, stderr = [
        "\n".join(line_iter)
        for line_iter in job_run.decoded_start_result_stdout_and_stderr_line_iters
    ]
    c_stdout, c_stderr = await asyncio.gather(c.log(stdout=True), c.log(stderr=True))
    log.debug(f"{container_name} stdout: {c_stdout}")
    log.debug(f"{container_name} stderr: {c_stderr}")
    return {
        "name": task.name,
        "command": task.command,
        "container_name": container_name,
        "working_dir": working_dir,
        "exit_code": last_inspect["ExitCode"],
        "stdout": stdout,
        "stderr": stderr,
    }


def iter_task_envs(
    config: RunRepoTasksConfig,
) -> Generator[
    Tuple[Language, PackageManager, DockerImage, ChainMap, List[ContainerTask]],
    None,
    None,
]:
    enabled_languages = config["languages"] or language_names
    if not config["languages"]:
        log.debug(f"languages not specified using all of {enabled_languages}")

    enabled_package_managers = config["package_managers"] or package_manager_names
    if not config["package_managers"]:
        log.debug(
            f"package managers not specified using all of {enabled_package_managers}"
        )

    enabled_image_names = config["docker_images"] or docker_image_names
    if not config["docker_images"]:
        log.debug(
            f"docker image names not specified using all of {enabled_image_names}"
        )

    for language_name, package_manager_name, image_name in itertools.product(
        enabled_languages, enabled_package_managers, enabled_image_names
    ):
        if language_name not in languages:
            continue
        language = languages[language_name]
        if package_manager_name not in language.package_managers:
            continue
        package_manager = language.package_managers[package_manager_name]
        if image_name not in language.images:
            continue
        image = language.images[image_name]

        version_commands = ChainMap(
            language.version_commands,
            *[pm.version_commands for pm in language.package_managers.values()],
        )
        tasks: List[ContainerTask] = [
            package_manager.tasks[task_name] for task_name in config["repo_tasks"]
        ]
        yield language, package_manager, image, version_commands, tasks
