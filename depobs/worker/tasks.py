import datetime
import os
import sys
import re
import subprocess
from typing import List, Tuple, Union, Optional
import logging

from celery import Celery
from celery.exceptions import (
    SoftTimeLimitExceeded,
    TimeLimitExceeded,
    WorkerLostError,
    WorkerShutdown,
    WorkerTerminate,
)
import celery.result

import depobs.worker.celeryconfig as celeryconfig

from depobs.website.models import (
    PackageReport,
    PackageLatestReport,
    get_package_report,
    get_npms_io_score,
    get_NPMRegistryEntry,
    get_maintainers_contributors,
    get_npm_registry_data,
    get_direct_dependencies,
    get_vulnerability_counts,
    get_direct_dependency_reports,
    store_package_report,
    get_ordered_package_deps,
)

from depobs.database.schema import (
    Base,
    Advisory,
    PackageVersion,
    PackageLink,
    PackageGraph,
    NPMSIOScore,
    NPMRegistryEntry,
)

log = logging.getLogger("depobs.worker")
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

# Create the scanner task queue
scanner = Celery(
    "tasks",
    broker=os.environ["CELERY_BROKER_URL"],
    result_backend=os.environ["CELERY_RESULT_BACKEND"],
)
scanner.config_from_object(celeryconfig)

# The name must be less than or equal to 214 characters. This includes the scope for scoped packages.
# The name can’t start with a dot or an underscore.
# New packages must not have uppercase letters in the name.
# The name ends up being part of a URL, an argument on the command line, and a folder name. Therefore, the name can’t contain any non-URL-safe characters.
#
# https://docs.npmjs.com/files/package.json#name
NPM_PACKAGE_NAME_RE = re.compile(
    r"""[@a-zA-Z0-9][\.-_@/a-zA-Z0-9]{0,213}""", re.VERBOSE,
)


def get_npm_package_name_validation_error(package_name: str) -> Optional[Exception]:
    """returns an Exception if package name is invalid or None if it is valid"""
    if not isinstance(package_name, str):
        return Exception("Invalid NPM package name. Must be a str.")

    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        return Exception(
            f"Invalid NPM package name. Must match {NPM_PACKAGE_NAME_RE.pattern!r}"
        )

    return None


# Version must be parseable by node-semver, which is bundled with npm as a dependency.
#
# https://docs.npmjs.com/files/package.json#version
#
# https://docs.npmjs.com/misc/semver#versions
NPM_PACKAGE_VERSION_RE = re.compile(
    r"""(=v)?           # strip leading = and v
[0-9]+\.[0-9]+\.[0-9]+  # major minor and patch versions (TODO: check if positive ints)
[-]?[-\.0-9A-Za-z]*       # optional pre-release version e.g. -alpha.1 (TODO: split out identifiers)
[+]?[-\.0-9A-Za-z]*       # optional build metadata e.g. +exp.sha.5114f85
""",
    re.VERBOSE,
)


def get_npm_package_version_validation_error(package_name: str) -> Optional[Exception]:
    """returns an Exception if package version is invalid or None if it is valid"""
    if not isinstance(package_name, str):
        return Exception("Invalid NPM package version. Must be a str.")

    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        return Exception(
            f"Invalid NPM package version. Must match {NPM_PACKAGE_VERSION_RE.pattern!r}"
        )

    return None


@scanner.task()
def add(x, y):
    return x + y


@scanner.task()
def scan_npm_package(
    package_name: str, package_version: Optional[str] = None
) -> None:
    package_name_validation_error = get_npm_package_name_validation_error(package_name)
    if package_name_validation_error is not None:
        raise package_name_validation_error

    if package_version:
        package_version_validation_error = get_npm_package_version_validation_error(
            package_version
        )
        if package_version_validation_error is not None:
            raise package_version_validation_error

    # mozilla/dependencyscan:latest must already be built/pulled/otherwise
    # present on the worker node
    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        f"DB_URL={os.environ['DATABASE_URI']}",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "mozilla/dependencyscan:latest",
        "analyze_package.sh",
        package_name,
    ]
    if package_version:
        command.append(package_version)

    log.info(f"running {command} for package_name {package_name}@{package_version}")
    subprocess.run(command, encoding="utf-8", capture_output=True).check_returncode()
    return (package_name, package_version)


@scanner.task()
def score_package(package_name: str, package_version: str):
    pr = PackageReport()
    pr.package = package_name
    pr.version = package_version

    plr = PackageLatestReport()
    plr.package = package_name
    plr.version = package_version

    stmt = get_npms_io_score(package_name, package_version)
    pr.npmsio_score = stmt.first()

    pr.directVulnsCritical_score = 0
    pr.directVulnsHigh_score = 0
    pr.directVulnsMedium_score = 0
    pr.directVulnsLow_score = 0

    # Direct vulnerability counts
    stmt = get_vulnerability_counts(package_name, package_version)
    for package, version, severity, count in stmt:
        # This is not yet tested - need real data
        print("\t" + package + "\t" + version + "\t" + severity + "\t" + str(count))
        if severity == "critical":
            pr.directVulnsCritical_score = count
        elif severity == "high":
            pr.directVulnsHigh_score = count
        elif severity == "medium":
            pr.directVulnsMedium_score = count
        elif severity == "low":
            pr.directVulnsLow_score = count
        else:
            log.error(
                f"unexpected severity {severity} for package {package} / version {version}"
            )

    stmt = get_npm_registry_data(package_name, package_version)
    for published_at, maintainers, contributors in stmt:
        pr.release_date = published_at
        if maintainers is not None:
            pr.authors = len(maintainers)
        else:
            pr.authors = 0
        if contributors is not None:
            pr.contributors = len(contributors)
        else:
            pr.contributors = 0

    pr.immediate_deps = get_direct_dependencies(package_name, package_version).count()

    # Indirect counts
    pr.all_deps = 0
    stmt = get_direct_dependency_reports(package_name, package_version)
    pr.indirectVulnsCritical_score = 0
    pr.indirectVulnsHigh_score = 0
    pr.indirectVulnsMedium_score = 0
    pr.indirectVulnsLow_score = 0

    dep_rep_count = 0
    for (
        package,
        version,
        scoring_date,
        top_score,
        all_deps,
        directVulnsCritical_score,
        directVulnsHigh_score,
        directVulnsMedium_score,
        directVulnsLow_score,
        indirectVulnsCritical_score,
        indirectVulnsHigh_score,
        indirectVulnsMedium_score,
        indirectVulnsLow_score,
    ) in stmt:
        dep_rep_count += 1
        pr.all_deps += 1 + all_deps
        pr.indirectVulnsCritical_score += (
            directVulnsCritical_score + indirectVulnsCritical_score
        )
        pr.indirectVulnsHigh_score += directVulnsHigh_score + indirectVulnsHigh_score
        pr.indirectVulnsMedium_score += (
            directVulnsMedium_score + indirectVulnsMedium_score
        )
        pr.indirectVulnsLow_score += directVulnsLow_score + indirectVulnsLow_score

    if dep_rep_count != pr.immediate_deps:
        log.error(
            f"expected {pr.immediate_deps} dependencies but got {dep_rep_count} for package {package_name} / version {package_version}"
        )

    pr.scoring_date = datetime.datetime.now()

    store_package_report(pr)


@scanner.task()
def build_report_tree(package_version_tuple: Tuple[str, str]):
    package_name, package_version = package_version_tuple
    deps = get_ordered_package_deps(package_name, package_version)
    if len(deps) == 0:
        score_package.delay(package_name, package_version)
    else:
        for (dep_name, dep_version) in deps:
            print("will build report tree  for %s %s", (dep_name, dep_version))
            build_report_tree.delay((dep_name, dep_version))


@scanner.task()
def scan_npm_package_then_build_report_tree(
    package_name: str, package_version: Optional[str] = None
) -> celery.result.AsyncResult:
    return scan_npm_package.apply_async(args=(package_name, package_version), link=build_report_tree.signature())
