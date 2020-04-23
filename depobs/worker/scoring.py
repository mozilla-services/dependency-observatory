from datetime import datetime
import logging
from typing import Dict, List

import networkx as nx
from networkx.algorithms.dag import descendants

from depobs.scanner.db.schema import PackageVersion
from depobs.scanner.graph_traversal import outer_in_iter
from depobs.website.models import (
    PackageReport,
    PackageLatestReport,
    get_npms_io_score,
    get_npm_registry_data,
    get_vulnerability_counts,
)

log = logging.getLogger(__name__)


def score_package(
    package_name: str,
    package_version: str,
    direct_dep_reports: List[PackageReport],
    all_deps_count: int = 0,
) -> PackageReport:
    log.info(
        f"scoring package: {package_name}@{package_version} with direct deps {list((r.package, r.version) for r in direct_dep_reports)}"
    )
    pr = PackageReport()
    pr.package = package_name
    pr.version = package_version

    plr = PackageLatestReport()
    plr.package = package_name
    plr.version = package_version

    # NB: raises for a missing score
    pr.npmsio_score = get_npms_io_score(package_name, package_version).first()

    pr.directVulnsCritical_score = 0
    pr.directVulnsHigh_score = 0
    pr.directVulnsMedium_score = 0
    pr.directVulnsLow_score = 0

    # Direct vulnerability counts
    for package, version, severity, count in get_vulnerability_counts(
        package_name, package_version
    ):
        severity = severity.lower()
        log.info(
            f"scoring package: {package_name}@{package_version} found vulnerable dep: \t{package}\t{version}\t{severity}\t{count}"
        )
        if severity == "critical":
            pr.directVulnsCritical_score = count
        elif severity == "high":
            pr.directVulnsHigh_score = count
        elif severity in ("medium", "moderate"):
            pr.directVulnsMedium_score = count
        elif severity == "low":
            pr.directVulnsLow_score = count
        else:
            log.error(
                f"unexpected severity {severity} for package {package} / version {version}"
            )

    for published_at, maintainers, contributors in get_npm_registry_data(
        package_name, package_version
    ):
        pr.release_date = published_at
        if maintainers is not None:
            pr.authors = len(maintainers)
        else:
            pr.authors = 0
        if contributors is not None:
            pr.contributors = len(contributors)
        else:
            pr.contributors = 0

    pr.immediate_deps = len(direct_dep_reports)
    pr.all_deps = all_deps_count

    # Indirect counts
    pr.indirectVulnsCritical_score = 0
    pr.indirectVulnsHigh_score = 0
    pr.indirectVulnsMedium_score = 0
    pr.indirectVulnsLow_score = 0

    for report in direct_dep_reports:
        for severity in ("Critical", "High", "Medium", "Low"):
            current_count = getattr(pr, f"indirectVulns{severity}_score", 0)
            dep_vuln_count = (
                getattr(report, f"directVulns{severity}_score", 0) or 0
            ) + (getattr(report, f"indirectVulns{severity}_score", 0) or 0)
            setattr(
                pr, f"indirectVulns{severity}_score", current_count + dep_vuln_count,
            )
        pr.dependencies.append(report)

    pr.scoring_date = datetime.now()
    pr.status = "scanned"
    return pr


def score_package_and_children(
    g: nx.DiGraph, package_versions: List[PackageVersion]
) -> List[PackageReport]:
    # refs: https://github.com/mozilla-services/dependency-observatory/issues/130#issuecomment-608017713
    package_versions_by_id: Dict[int, PackageVersion] = {
        pv.id: pv for pv in package_versions
    }
    # fill this up
    package_reports_by_id: Dict[int, PackageReport] = {}

    for package_version_ids in outer_in_iter(g):
        for package_version_id in package_version_ids:
            package = package_versions_by_id[package_version_id]
            package_reports_by_id[package_version_id] = score_package(
                package.name,
                package.version,
                direct_dep_reports=[
                    package_reports_by_id[direct_dep_package_version_id]
                    for direct_dep_package_version_id in g.successors(
                        package_version_id
                    )
                ],
                all_deps_count=len(descendants(g, package_version_id)),
            )

    return list(package_reports_by_id.values())
