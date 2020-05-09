from dataclasses import asdict
import json
import logging
from typing import (
    AbstractSet,
    Any,
    AnyStr,
    AsyncGenerator,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from depobs.database.models import NPMRegistryEntry
from depobs.scanner.graph_util import npm_packages_to_networkx_digraph, get_graph_stats
from depobs.scanner.models.org_repo import OrgRepo
from depobs.scanner.models.git_ref import GitRef
from depobs.scanner.models.language import (
    DependencyFile,
    languages,
    ContainerTask,
    package_managers,
)
from depobs.scanner.models.nodejs import NPMPackage, flatten_deps
from depobs.util.serialize_util import (
    get_in,
    extract_fields,
    extract_nested_fields,
    iter_jsonlines,
)


log = logging.getLogger(__name__)


def parse_stdout_as_json(stdout: Optional[str]) -> Optional[Dict]:
    if stdout is None:
        return None

    try:
        parsed_stdout = json.loads(stdout)
        return parsed_stdout
    except json.decoder.JSONDecodeError as e:
        log.warn(f"error parsing stdout as JSON: {e}")

    return None


def parse_stdout_as_jsonlines(stdout: Optional[str]) -> Optional[Sequence[Dict]]:
    if stdout is None:
        return None

    try:
        return list(
            line
            for line in iter_jsonlines(stdout.split("\n"))
            if isinstance(line, dict)
        )
    except json.decoder.JSONDecodeError as e:
        log.warn(f"error parsing stdout as JSON: {e}")

    return None


def parse_npm_list(parsed_stdout: Dict) -> Dict:
    deps = [dep for dep in flatten_deps(parsed_stdout)]
    updates = {"problems": get_in(parsed_stdout, ["problems"], [])}
    updates["dependencies"] = [asdict(dep) for dep in deps]
    updates["dependencies_count"] = len(deps)
    updates["problems_count"] = len(updates["problems"])

    updates["root"] = asdict(deps[-1]) if len(deps) else None
    updates["direct_dependencies_count"] = (
        len(deps[-1].dependencies) if len(deps) else None
    )
    updates["graph_stats"] = (
        get_graph_stats(npm_packages_to_networkx_digraph(deps)) if deps else dict()
    )
    return updates


def parse_yarn_list(parsed_stdout: Sequence[Dict]) -> Optional[Dict]:
    updates: Dict = dict(dependencies=[])
    deps: List[NPMPackage] = []
    for line in parsed_stdout:
        line_type, line_data = line.get("type", None), line.get("data", dict())
        if line_type == "tree":
            deps.extend(
                NPMPackage.from_yarn_tree_line(dep) for dep in line_data["trees"]
            )
        else:
            # TODO: populate "problems" to match npm list field?
            log.warn(
                f"got unexpected yarn list line type: {line_type} with data {line_data}"
            )
    updates["dependencies"] = [asdict(dep) for dep in deps]
    updates["dependencies_count"] = len(deps)

    # yarn list doesn't include the root e.g. taskcluster
    updates["root"] = None
    updates["direct_dependencies_count"] = None

    # TODO: make sure we're actually resolving a graph
    updates["graph_stats"] = dict()
    return updates


def parse_npm_audit(parsed_stdout: Dict) -> Dict:
    # has format:
    # {
    #   actions: ...
    #   advisories: null or {
    #     <npm adv. id>: {
    # metadata: null also has an exploitablity score
    #
    # } ...
    #   }
    #   metadata: null or e.g. {
    #     "vulnerabilities": {
    #         "info": 0,
    #         "low": 0,
    #         "moderate": 6,
    #         "high": 0,
    #         "critical": 0
    #     },
    #     "dependencies": 896680,
    #     "devDependencies": 33885,
    #     "optionalDependencies": 10215,
    #     "totalDependencies": 940274
    #   }
    # }
    updates = extract_nested_fields(
        parsed_stdout,
        {
            "dependencies_count": ["metadata", "dependencies"],
            "dev_dependencies_count": ["metadata", "devDependencies"],
            "optional_dependencies_count": ["metadata", "optionalDependencies"],
            "total_dependencies_count": ["metadata", "totalDependencies"],
            "vulnerabilities": ["metadata", "vulnerabilities"],
            "advisories": ["advisories"],
            "error": ["error"],
        },
    )
    updates["advisories"] = (
        dict() if updates["advisories"] is None else updates["advisories"]
    )
    updates["vulnerabilities"] = (
        dict() if updates["vulnerabilities"] is None else updates["vulnerabilities"]
    )
    updates["vulnerabilities_count"] = sum(updates["vulnerabilities"].values())
    return updates


def parse_yarn_audit(parsed_stdout: Sequence[Dict]) -> Optional[Dict]:
    updates: Dict = dict(advisories=[])
    for line in parsed_stdout:
        line_type, line_data = line.get("type", None), line.get("data", dict())
        if line_type == "auditAdvisory":
            # TODO: normalize w/ npm advisory output
            updates["advisories"].append(line_data)
        elif line_type == "auditSummary":
            updates.update(
                extract_nested_fields(
                    line_data,
                    {
                        "dependencies_count": ["dependencies"],
                        "dev_dependencies_count": ["devDependencies"],
                        "optional_dependencies_count": ["optionalDependencies"],
                        "total_dependencies_count": ["totalDependencies"],
                        "vulnerabilities": ["vulnerabilities"],
                    },
                )
            )
            updates["vulnerabilities_count"] = sum(updates["vulnerabilities"].values())
        else:
            # TODO: populate "error": ["error"], to match npm audit error field?
            log.warn(
                f"got unexpected yarn audit line type: {line_type} with data {line_data}"
            )
    return updates


def parse_npm_task(task_name: str, task_result: Dict) -> Optional[Dict]:
    # TODO: reuse cached results for each set of dep files w/ hashes and task name
    parsed_stdout = parse_stdout_as_json(get_in(task_result, ["stdout"], None))
    if parsed_stdout is None:
        log.warn("got non-JSON stdout for npm")
        return None

    if task_name == "list_metadata":
        return parse_npm_list(parsed_stdout)
    elif task_name == "audit":
        return parse_npm_audit(parsed_stdout)
    elif task_name == "install":
        return None
    else:
        raise NotImplementedError()


def parse_yarn_task(task_name: str, task_result: Dict) -> Optional[Dict]:
    parsed_stdout = parse_stdout_as_jsonlines(get_in(task_result, ["stdout"], None))
    if parsed_stdout is None:
        log.warn("got non-JSON lines stdout for yarn")
        return None

    if task_name == "list_metadata":
        return parse_yarn_list(parsed_stdout)
    elif task_name == "audit":
        return parse_yarn_audit(parsed_stdout)
    elif task_name == "install":
        return None
    else:
        raise NotImplementedError()


def parse_cargo_list_metadata(parsed_stdout: Dict):
    if parsed_stdout.get("version", None) != 1:
        log.warn(
            f"unsupported cargo metadata version {parsed_stdout.get('version', None)}"
        )

    updates = extract_nested_fields(
        parsed_stdout,
        {
            # also workspace_root
            "root": ["resolve", "root"],  # str of pkg id; nullable
            "dependencies": ["resolve", "nodes"],  # array
            # rust specific
            "packages": ["packages"],  # additional data parsed from the Cargo.toml file
            "target_directory": ["target_directory"],  # file path in the container
            "workspace_root": ["workspace_root"],  # file path in the container
            "workspace_members": ["workspace_memebers"],  # list strs pkg ids
        },
    )
    # id: str, features: Seq[str], deps[{}]
    NODE_FIELDS = {"id", "features", "deps"}
    updates["dependencies"] = [
        extract_fields(node, NODE_FIELDS) for node in updates["dependencies"]
    ]
    updates["dependencies_count"] = len(updates["dependencies"])
    return updates


def parse_cargo_audit(parsed_stdout: Dict) -> Dict:
    return extract_nested_fields(
        parsed_stdout,
        {
            "dependencies_count": ["lockfile", "dependency-count"],
            "vulnerabilities_count": ["vulnerabilities", "count"],
            "advisories": ["vulnerabilities", "list"],
            "warnings": ["warnings"],  # list informational/low sev advisories
        },
    )


def parse_cargo_task(task_name: str, task_result: Dict) -> Optional[Dict]:
    parsed_stdout = parse_stdout_as_json(get_in(task_result, ["stdout"], None))
    if parsed_stdout is None:
        log.warn("got non-JSON stdout for cargo task")
        return None

    if task_name == "list_metadata":
        return parse_cargo_list_metadata(parsed_stdout)
    elif task_name == "audit":
        return parse_cargo_audit(parsed_stdout)
    elif task_name == "install":
        return None
    else:
        raise NotImplementedError()


def parse_command(task_name: str, task_command: str, task_data: Dict) -> Optional[Dict]:
    for package_manager_name, package_manager in package_managers.items():
        if any(task_command == task.command for task in package_manager.tasks.values()):
            if package_manager_name == "npm":
                return parse_npm_task(task_name, task_data)
            elif package_manager_name == "yarn":
                return parse_yarn_task(task_name, task_data)
            elif package_manager_name == "cargo":
                return parse_cargo_task(task_name, task_data)
    log.warning(f"unrecognized command {task_command}")
    return None


def serialize_repo_task(
    task_data: Dict[str, Any], task_names_to_process: AbstractSet[str],
) -> Optional[Dict[str, Any]]:
    # filter for node list_metadata output to parse and flatten deps
    task_name = get_in(task_data, ["name"], None)
    if task_name not in task_names_to_process:
        return None

    task_command = get_in(task_data, ["command"], None)

    task_result = extract_fields(
        task_data, ["command", "container_name", "exit_code", "name", "working_dir",],
    )

    updates = parse_command(task_name, task_command, task_data)
    if updates:
        if task_name == "list_metadata":
            log.info(
                f"wrote {task_result['name']} w/"
                f" {updates['dependencies_count']} deps and {updates.get('problems_count', 0)} problems"
                # f" {updates['graph_stats']}"
            )
        elif task_name == "audit":
            log.info(
                f"wrote {task_result['name']} w/ {updates['vulnerabilities_count']} vulns"
            )
        task_result.update(updates)
    return task_result


def serialize_npm_registry_entries(
    npm_registry_entries: Iterable[Dict[str, Any]]
) -> Iterable[NPMRegistryEntry]:
    for entry in npm_registry_entries:
        # save version specific data
        for version, version_data in entry["versions"].items():
            fields = extract_nested_fields(
                version_data,
                {
                    "package_name": ["name"],
                    "package_version": ["version"],
                    "shasum": ["dist", "shasum"],
                    "tarball": ["dist", "tarball"],
                    "git_head": ["gitHead"],
                    "repository_type": ["repository", "type"],
                    "repository_url": ["repository", "url"],
                    "description": ["description"],
                    "url": ["url"],
                    "license_type": ["license"],
                    "keywords": ["keywords"],
                    "has_shrinkwrap": ["_hasShrinkwrap"],
                    "bugs_url": ["bugs", "url"],
                    "bugs_email": ["bugs", "email"],
                    "author_name": ["author", "name"],
                    "author_email": ["author", "email"],
                    "author_url": ["author", "url"],
                    "maintainers": ["maintainers"],
                    "contributors": ["contributors"],
                    "publisher_name": ["_npmUser", "name"],
                    "publisher_email": ["_npmUser", "email"],
                    "publisher_node_version": ["_nodeVersion"],
                    "publisher_npm_version": ["_npmVersion"],
                },
            )
            # license can we a string e.g. 'MIT'
            # or dict e.g. {'type': 'MIT', 'url': 'https://github.com/jonschlinkert/micromatch/blob/master/LICENSE'}
            fields["license_url"] = None
            if isinstance(fields["license_type"], dict):
                fields["license_url"] = fields["license_type"].get("url", None)
                fields["license_type"] = fields["license_type"].get("type", None)

            # looking at you debuglog@0.0.{3,4} with:
            # [{"name": "StrongLoop", "url": "http://strongloop.com/license/"}, "MIT"],
            if not (
                (
                    isinstance(fields["license_type"], str)
                    or fields["license_type"] is None
                )
                and (
                    isinstance(fields["license_url"], str)
                    or fields["license_url"] is None
                )
            ):
                log.warning(f"skipping weird license format {fields['license_type']}")
                fields["license_url"] = None
                fields["license_type"] = None

            # published_at .time[<version>] e.g. '2014-05-23T21:21:04.170Z' (not from
            # the version info object)
            # where time: an object mapping versions to the time published, along with created and modified timestamps
            fields["published_at"] = get_in(entry, ["time", version])
            fields["package_modified_at"] = get_in(entry, ["time", "modified"])

            fields[
                "source_url"
            ] = f"https://registry.npmjs.org/{fields['package_name']}"
            yield NPMRegistryEntry(**fields)
