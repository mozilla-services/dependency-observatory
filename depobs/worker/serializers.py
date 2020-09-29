from dataclasses import asdict
import logging
from typing import (
    AbstractSet,
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from depobs.database.models import (
    Advisory,
    JSONResult,
    NPMRegistryEntry,
    NPMSIOScore,
    PackageGraph,
    PackageVersion,
)
from depobs.util.graph_util import npm_packages_to_networkx_digraph, get_graph_stats
from depobs.models.nodejs import NPMPackage, flatten_deps
from depobs.util.serialize_util import (
    extract_fields,
    extract_nested_fields,
    get_in,
    parse_stdout_as_json,
    parse_stdout_as_jsonlines,
)

log = logging.getLogger(__name__)


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
    package_manager_name = get_in(task_data, ["envvar_args", "PACKAGE_MANAGER"])
    if package_manager_name == "npm":
        return parse_npm_task(task_name, task_data)
    elif package_manager_name == "yarn":
        return parse_yarn_task(task_name, task_data)
    elif package_manager_name == "cargo":
        return parse_cargo_task(task_name, task_data)
    log.warning(f"unrecognized command {task_command}")
    return None


def serialize_repo_task(
    task_data: Dict[str, Any],
    task_names_to_process: AbstractSet[str],
) -> Optional[Dict[str, Any]]:
    # filter for node list_metadata output to parse and flatten deps
    task_name = get_in(task_data, ["name"], None)
    if task_name not in task_names_to_process:
        return None

    task_command = get_in(task_data, ["command"], None)

    task_result = extract_fields(
        task_data,
        [
            "command",
            "exit_code",
            "name",
            "working_dir",
        ],
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


def serialize_npm_registry_constraints(
    version_data: Dict[str, Any]
) -> List[Dict[str, str]]:
    constraints = []
    for prefix, constraint_field in (
        ("", "dependencies"),
        ("optional", "optionalDependencies"),
        ("dev", "devDependencies"),
        ("peer", "peerDependencies"),
    ):
        field_data = get_in(version_data, [constraint_field])
        if field_data is None:
            continue
        if not isinstance(field_data, dict):
            log.warn(
                "got unexpected dependencies data type for {prefix} {constraint_field} {type(field_data)}"
            )
            continue

        for name, version_range in field_data.items():
            constraints.append(
                dict(name=name, version_range=version_range, type_prefix=prefix)
            )
    return constraints


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
                    "scripts": ["scripts"],
                },
            )
            fields["constraints"] = serialize_npm_registry_constraints(version_data)
            log.debug(
                f"serialized npm registry constraints for {fields['package_name']}@{fields['package_version']} : {fields['constraints']}"
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


def serialize_npmsio_scores(
    npmsio_scores: Iterable[Dict[str, Any]]
) -> Iterable[NPMSIOScore]:
    for score in npmsio_scores:
        fields = extract_nested_fields(
            score,
            {
                "package_name": ["collected", "metadata", "name"],
                "package_version": ["collected", "metadata", "version"],
                "analyzed_at": ["analyzedAt"],  # e.g. "2019-11-27T19:31:42.541Z"
                # overall score from .score.final on the interval [0, 1]
                "score": ["score", "final"],
                # score components on the interval [0, 1]
                "quality": ["score", "detail", "quality"],
                "popularity": ["score", "detail", "popularity"],
                "maintenance": ["score", "detail", "maintenance"],
                # score subcomponent/detail fields from .evaluation.<component>.<subcomponent>
                # generally frequencies and subscores are decimals between [0, 1]
                # or counts of downloads, stars, etc.
                # acceleration is signed (+/-)
                "branding": ["evaluation", "quality", "branding"],
                "carefulness": ["evaluation", "quality", "carefulness"],
                "health": ["evaluation", "quality", "health"],
                "tests": ["evaluation", "quality", "tests"],
                "community_interest": ["evaluation", "popularity", "communityInterest"],
                "dependents_count": ["evaluation", "popularity", "dependentsCount"],
                "downloads_acceleration": [
                    "evaluation",
                    "popularity",
                    "downloadsAcceleration",
                ],
                "downloads_count": ["evaluation", "popularity", "downloadsCount"],
                "commits_frequency": ["evaluation", "maintenance", "commitsFrequency"],
                "issues_distribution": [
                    "evaluation",
                    "maintenance",
                    "issuesDistribution",
                ],
                "open_issues": ["evaluation", "maintenance", "openIssues"],
                "releases_frequency": [
                    "evaluation",
                    "maintenance",
                    "releasesFrequency",
                ],
            },
        )
        fields[
            "source_url"
        ] = f"https://api.npms.io/v2/package/{fields['package_name']}"
        yield NPMSIOScore(**fields)


def get_advisory_impacted_versions(advisory_json: Dict) -> Set[str]:
    """
    Extracts the findings field listing impacted versions for an
    advisory from npm audit JSON output
    """
    impacted_versions = set(
        finding.get("version", None)
        for finding in advisory_json.get("findings", [])  # NB: not an Advisory model
        if finding.get("version", None)
    )
    return impacted_versions


def node_repo_task_audit_output_to_advisories_and_impacted_versions(
    task_data: Dict,
) -> Iterable[Tuple[Advisory, AbstractSet[str]]]:
    is_yarn_cmd = bool("yarn" in task_data["command"])
    # NB: yarn has .advisory and .resolution

    # the same advisory JSON (from the npm DB) is
    # at .advisories{k, v} for npm and .advisories[].advisory for yarn
    advisory_fields = (
        (item.get("advisory", None) for item in task_data.get("advisories", []))
        if is_yarn_cmd
        else task_data.get("advisories", dict()).values()
    )
    return (
        (adv, get_advisory_impacted_versions(adv)) for adv in advisory_fields if adv
    )


def serialize_advisories(advisories_data: Iterable[Dict]) -> Iterable[Advisory]:
    for advisory_data in advisories_data:
        advisory_fields = extract_nested_fields(
            advisory_data,
            {
                "package_name": ["module_name"],
                "npm_advisory_id": ["id"],
                "vulnerable_versions": ["vulnerable_versions"],
                "patched_versions": ["patched_versions"],
                "created": ["created"],
                "updated": ["updated"],
                "url": ["url"],
                "severity": ["severity"],
                "cves": ["cves"],
                "cwe": ["cwe"],
                "exploitability": ["metadata", "exploitability"],
                "title": ["title"],
            },
        )
        cwe_id = advisory_fields["cwe"].lower().replace("cwe-", "")
        advisory_fields["cwe"] = int(cwe_id) if cwe_id else None
        advisory_fields["language"] = "node"
        advisory_fields["vulnerable_package_version_ids"] = []
        yield Advisory(**advisory_fields)


def deserialize_npm_package_version(package: Dict[str, str]) -> PackageVersion:
    """
    Deserializes a dict from npm list output into a PackageVersion
    """
    return PackageVersion(
        name=package.get("name", None),
        version=package.get("version", None),
        language="node",
        url=package.get(
            "resolved", None
        ),  # is null for the root for npm list and yarn list output
    )


def deserialize_scan_job_results(
    messages: Iterable[JSONResult],
) -> Generator[
    Union[
        PackageVersion,
        Tuple[
            PackageGraph,
            Optional[PackageVersion],
            List[Tuple[PackageVersion, PackageVersion]],
        ],
        Tuple[Advisory, AbstractSet[str]],
    ],
    None,
    None,
]:
    """Takes an iterable of JSONResults of pubsub messages for a
    completed npm scan (tarball or dep file), parses the messages, and
    yields models to save in the following order:

    * one or more PackageVersions
    * a PackageGraph with an optional root package version and a list of its links in a pairs of PackageVersions
    * Advisory models with impacted versions (if any)

    The models will not have IDs and should be upserted to avoid
    violating index constraints and creating duplicate rows.
    """
    for json_result in messages:
        if json_result.data is None:
            log.warning(f"json result ID: {json_result.id} null data column")
            continue
        if not isinstance(json_result.data, dict):
            log.warn(f"json result ID: {json_result.id} non-dict data column")
            continue
        if (
            json_result.data.get("type", None)
            != "google.cloud.pubsub_v1.types.PubsubMessage"
        ):
            log.warn(
                f"json result ID: {json_result.id} invalid type (not PubsubMessage)"
            )
            continue

        for line in json_result.data["data"]:
            if not isinstance(line, dict):
                continue
            if line.get("type", None) != "task_result":
                continue

            task_data: Optional[Dict[str, Any]] = serialize_repo_task(
                line, {"list_metadata", "audit"}
            )
            if not task_data:
                continue

            task_name = line["name"]
            if task_name == "list_metadata":
                links: List[Tuple[PackageVersion, PackageVersion]] = []
                for task_dep in task_data.get("dependencies", []):
                    parent: PackageVersion = deserialize_npm_package_version(task_dep)
                    yield parent
                    for dep in task_dep.get("dependencies", []):
                        # is fully qualified semver for npm (or file: or github: url), semver for yarn
                        name, version = dep.rsplit("@", 1)
                        child: PackageVersion = deserialize_npm_package_version(
                            dict(
                                name=name,
                                version=version,
                            )
                        )
                        yield child
                        links.append((parent, child))
                package_manager = "yarn" if "yarn" in task_data["command"] else "npm"
                root_package_version = (
                    deserialize_npm_package_version(task_data["root"])
                    if task_data["root"]
                    else None
                )
                # NB: caller must convert links to link_ids, root_package_version to root_package_version_id
                yield PackageGraph(
                    root_package_version_id=None,
                    link_ids=[],
                    package_manager=package_manager,
                    package_manager_version=None,  # TODO: find and set
                ), root_package_version, links
            elif task_name == "audit":
                for (
                    advisory_fields,
                    impacted_versions,
                ) in node_repo_task_audit_output_to_advisories_and_impacted_versions(
                    task_data
                ):
                    advisory: Advisory = list(serialize_advisories([advisory_fields]))[
                        0
                    ]
                    yield advisory, impacted_versions
            else:
                log.warning(f"skipping unrecognized task {task_name}")
