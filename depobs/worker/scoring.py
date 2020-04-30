from datetime import datetime
from collections import Counter
from datetime import datetime
import enum
import logging
from typing import Dict, List, Optional, Tuple, Union

import networkx as nx
from networkx.algorithms.dag import descendants

from depobs.scanner.graph_traversal import outer_in_dag_iter
from depobs.database.models import (
    Advisory,
    PackageReport,
    PackageVersion,
    get_npms_io_score,
    get_npm_registry_data,
    get_package_from_name_and_version,
    get_advisories_by_package_versions,
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

    package_version_obj: Optional[PackageVersion] = get_package_from_name_and_version(
        package_name, package_version
    )
    if package_version_obj is None:
        raise Exception(
            f"could not find PackageVersion to fetch vulnerabilities for {package_name}@{package_version}"
        )

    direct_vuln_counts = count_advisories_by_severity(
        get_advisories_by_package_versions([package_version_obj])
    )
    direct_vuln_counts.update(zeroed_severity_counter())
    indirect_distinct_vuln_counts = zeroed_severity_counter()
    # indirect_distinct_vuln_counts = count_advisories_by_severity(
    #     set(get_distinct_advisories_by_package_versions(direct_deps + indirect_deps))
    # )
    # indirect_distinct_vuln_counts.update(zeroed_severity_counter())

    npm_registry_data: Optional[
        Tuple[
            Optional[datetime],
            Optional[List[Union[Dict, str]]],
            Optional[List[Union[Dict, str]]],
        ]
    ] = get_npm_registry_data(
        package_name,
        package_version
        # refs #227
    ).one_or_none()  # type: ignore
    published_at, maintainers, contributors = None, None, None
    if npm_registry_data is not None:
        published_at, maintainers, contributors = npm_registry_data
        maintainers = maintainers if maintainers else []
        contributors = contributors if contributors else []

    pr = PackageReport(
        package=package_name,
        version=package_version,
        all_deps=all_deps_count,
        immediate_deps=len(direct_dep_reports),
        # NB: raises for a missing score
        # refs #227
        npmsio_score=get_npms_io_score(package_name, package_version).first(),  # type: ignore
        authors=len(maintainers) if maintainers is not None else None,
        contributors=len(contributors) if contributors is not None else None,
        release_date=published_at,
        scoring_date=datetime.now(),
        status="scanned",
        **{
            f"directVulns{severity.name.capitalize()}_score": count
            for (severity, count) in dict(direct_vuln_counts).items()
        },
        **{
            f"indirectVulns{severity.name.capitalize()}_score": count
            for (severity, count) in dict(indirect_distinct_vuln_counts).items()
        },
    )

    for report in direct_dep_reports:
        for severity in ("Critical", "High", "Medium", "Low"):
            current_count = getattr(pr, f"indirectVulns{severity}_score", 0)
            dep_vuln_count = (
                getattr(report, f"directVulns{severity}_score", 0) or 0
            ) + (getattr(report, f"indirectVulns{severity}_score", 0) or 0)
            setattr(
                pr, f"indirectVulns{severity}_score", current_count + dep_vuln_count,
            )

    pr.dependencies.extend(direct_dep_reports)
    return pr


def score_package_and_children(
    g: nx.DiGraph, package_versions: List[PackageVersion]
) -> List[PackageReport]:
    assert len(package_versions) >= len(g.nodes)
    # refs: https://github.com/mozilla-services/dependency-observatory/issues/130#issuecomment-608017713
    package_versions_by_id: Dict[int, PackageVersion] = {
        pv.id: pv for pv in package_versions
    }
    # fill this up
    package_reports_by_id: Dict[int, PackageReport] = {}

    for package_version_ids in outer_in_dag_iter(g):
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


class AdvisorySeverity(enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    # an alias for medium
    MODERATE = "medium"


def zeroed_severity_counter() -> Counter:
    """
    Returns a counter with zeroes for each AdvisorySeverity level
    """
    counter: Counter = Counter()
    for severity in AdvisorySeverity:
        counter[severity] = 0
    return counter


def count_advisories_by_severity(advisories: List[Advisory]) -> Counter:
    """Given a list of advisories returns a collections.Counter with
    counts for non-zero severities.

    Normalizes severity names according to the AdvisorySeverity
    enum. (e.g. treat "moderate" as MEDIUM)
    """
    counter = Counter(
        AdvisorySeverity[advisory.severity.upper()]
        for advisory in advisories
        if isinstance(advisory.severity, str)
        and advisory.severity.upper() in AdvisorySeverity.__members__.keys()
    )
    return counter
