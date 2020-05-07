import aiodocker
import asyncio
from collections import ChainMap
from dataclasses import asdict
import functools
import itertools
import json
import logging
import pathlib
from random import randrange
import sys
import time
from typing import (
    AbstractSet,
    Any,
    AnyStr,
    AsyncGenerator,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    TypedDict,
    Union,
)

from depobs.util.serialize_util import (
    get_in,
    extract_fields,
)
import depobs.scanner.docker.containers as containers
from depobs.scanner.models.org_repo import OrgRepo
from depobs.scanner.models.git_ref import GitRef
from depobs.scanner.docker.images import build_images
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
from depobs.scanner.pipelines.util import exc_to_str

log = logging.getLogger(__name__)

__doc__ = """Runs tasks on a checked out git ref with dep. files"""


class RunRepoTasksConfig(TypedDict):
    # pull base docker images before building them
    docker_pull: bool

    # build docker images
    docker_build: bool

    # Print commands we would run and their context, but don't run them.
    dry_run: bool

    # Run 'git clean -fdx' for each ref to clear package manager caches. Slower but better isolation.
    git_clean: bool # TODO: default to false

    # Cache and results for the same repo, and dep file directory and SHA2
    # sums for multiple git refs (NB: ignores changes to non-dep files e.g. to
    # node.js install hook scripts).
    use_cache: bool

    # Only run against matching directory. e.g. './' for root directory or
    # './packages/fxa-js-client/' for a subdirectory
    dir: str

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


async def run_task(
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


async def run_in_repo_at_ref(
    config: RunRepoTasksConfig,
    item: Tuple[OrgRepo, GitRef, pathlib.Path],
    tasks: List[ContainerTask],
    version_commands: Mapping[str, str],
    dry_run: bool,
    cwd_files: AbstractSet[str],
    file_rows: List[DependencyFile],
    image: DockerImage,
) -> AsyncGenerator[Dict[str, Any], None]:
    (org_repo, git_ref, path) = item

    container_name = f"dep-obs-nodejs-metadata-{org_repo.org}-{org_repo.repo}-{hex(randrange(1 << 32))[2:]}"
    async with containers.run(
        image.local.repo_name_tag, name=container_name, cmd="/bin/bash",
    ) as c:
        await c.run("mkdir -p /repos", wait=True, check=True)
        await containers.ensure_repo(
            c,
            org_repo.github_clone_url,
            git_clean=config["git_clean"],
            working_dir="/repos/",
        )
        await containers.ensure_ref(c, git_ref, working_dir="/repos/repo")
        branch, commit, tag, *version_results = await asyncio.gather(
            *(
                [
                    containers.get_branch(c, working_dir="/repos/repo"),
                    containers.get_commit(c, working_dir="/repos/repo"),
                    containers.get_tag(c, working_dir="/repos/repo"),
                ]
                + [
                    containers.run_container_cmd_no_args_return_first_line_or_none(
                        command, c, working_dir="/repos/repo"
                    )
                    for command in version_commands.values()
                ]
            )
        )
        versions = {
            command_name: version_results[i]
            for (i, (command_name, command)) in enumerate(version_commands.items())
        }

        if dry_run:
            for task in tasks:
                log.info(
                    f"{container_name} in {pathlib.Path('/repos/repo') / path} for task {task.name} skipping running {task.command} for dry run"
                )
        else:
            task_results = [
                await run_task(
                    c, task, str(pathlib.Path("/repos/repo") / path), container_name
                )
                for task in tasks
            ]
            for tr in task_results:
                if isinstance(tr, Exception):
                    log.error(f"error running task: {tr}")

            result: Dict[str, Any] = dict(
                org=org_repo.org,
                repo=org_repo.repo,
                ref=git_ref.to_dict(),
                repo_url=org_repo.github_clone_url,
                versions=versions,
                branch=branch,
                commit=commit,
                tag=tag,
                dependency_files=[fr.to_dict() for fr in file_rows],
                task_results=[tr for tr in task_results if isinstance(tr, dict)],
            )
            yield result


DepFileRow = Tuple[OrgRepo, GitRef, DependencyFile]


def group_by_org_repo_ref_path(
    source: Generator[Dict[str, Any], None, None]
) -> Generator[Tuple[Tuple[str, str, pathlib.Path], List[DepFileRow]], None, None]:
    # read all input rows into memory
    rows: List[DepFileRow] = [
        (
            OrgRepo(item["org"], item["repo"]),
            GitRef.from_dict(item["ref"]),
            DependencyFile.from_dict(item["dependency_file"]),
        )
        for item in source
    ]

    # sort in-place by org repo then ref value (sorted is stable)
    sorted(rows, key=lambda row: row[0].org_repo)
    sorted(rows, key=lambda row: row[1].value)

    # group by org repo then ref value
    for org_repo_ref_key, group_iter in itertools.groupby(
        rows, key=lambda row: (row[0].org_repo, row[1].value)
    ):
        org_repo_key, ref_value_key = org_repo_ref_key
        org_repo_ref_rows = list(group_iter)

        # sort and group by path parent e.g. /foo/bar for /foo/bar/package.json
        sorted(org_repo_ref_rows, key=lambda row: row[2].path.parent)
        for dep_file_parent_key, inner_group_iter in itertools.groupby(
            org_repo_ref_rows, key=lambda row: row[2].path.parent
        ):
            file_rows = list(inner_group_iter)
            yield (org_repo_key, ref_value_key, dep_file_parent_key), file_rows


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


async def build_images_for_envs(
    config: RunRepoTasksConfig,
    task_envs: List[
        Tuple[Language, PackageManager, DockerImage, ChainMap, List[ContainerTask]]
    ],
) -> None:
    image_keys: AbstractSet[str] = {
        image.local.repo_name_tag for (_, _, image, _, _) in task_envs
    }
    images: Iterable[DockerImage] = [
        docker_images[image_key] for image_key in image_keys
    ]
    log.info(
        f"building images: {[image.base.repo_name_tag + ' as ' + image.local.repo_name_tag for image in images]}"
    )
    built_image_tags: Iterable[str] = await build_images(config["docker_pull"], images)
    log.info(f"successfully built and tagged images {built_image_tags}")


async def run_pipeline(
    source: Generator[Dict[str, Any], None, None], config: RunRepoTasksConfig
) -> AsyncGenerator[Dict, None]:
    log.info(f"{__name__} pipeline started with config {config}")
    task_envs = list(iter_task_envs(config))
    if config["docker_build"]:
        await build_images_for_envs(config, task_envs)

    # cache of results by lang name, package manager name,
    # image.local.repo_name_tag, org/repo, dep files dir path, dep file sha256s
    cache: Dict[Tuple[str, str, str, str, pathlib.Path, str], List[Dict]] = {}
    for (
        (org_repo_key, ref_value_key, dep_file_parent_key),
        file_rows,
    ) in group_by_org_repo_ref_path(source):
        files = {fr[2].path.parts[-1] for fr in file_rows}
        file_hashes = sorted([fr[2].sha256 for fr in file_rows])
        dep_files = [fr[2] for fr in file_rows]

        org_repo, git_ref = file_rows[0][0:2]

        log.debug(f"in {dep_file_parent_key!r} with files {files}")
        if config["dir"] is not None:
            if pathlib.PurePath(config["dir"]) != dep_file_parent_key:
                log.debug(
                    f"Skipping non-matching folder {dep_file_parent_key} for glob {config['dir']}"
                )
                continue
            else:
                log.debug(
                    f"matching folder {dep_file_parent_key!r} for glob {config['dir']!r}"
                )

        for lang, pm, image, version_commands, tasks in task_envs:
            if config["dry_run"]:
                log.info(
                    f"for {lang.name} {pm.name} would run in {image.local.repo_name_tag}"
                    f" {org_repo_key} {git_ref.kind.name} {git_ref.value} {dep_file_parent_key}"
                    f" {list(version_commands.values())} concurrently then"
                    f" {[t.command for t in tasks]} "
                )
                continue

            # TODO: use caching decorator
            cache_key = (
                lang.name,
                pm.name,
                image.local.repo_name_tag,
                org_repo_key,
                dep_file_parent_key,
                "-".join(file_hashes),
            )
            if config["use_cache"] and cache_key in cache:
                log.debug(f"using cached result for {cache_key}")
                for cached_result in cache[cache_key]:
                    cached_result["data_source"] = "in_memory_cache"
                    yield cached_result
                continue

            cache[cache_key] = []
            try:
                async for result in run_in_repo_at_ref(
                    config,
                    (org_repo, git_ref, dep_file_parent_key),
                    tasks,
                    version_commands,
                    config["dry_run"],
                    files,
                    dep_files,
                    image,
                ):
                    cache[cache_key].append(result)
                    yield result
                log.debug(f"saved cached result for {cache_key}")
            except Exception as e:
                log.error(f"error running tasks {tasks!r}:\n{exc_to_str()}")
