from datetime import datetime
from collections import ChainMap, Counter
from datetime import datetime
import enum
import logging
from os.path import commonprefix
from typing import Any, Dict, List, Optional, Set, Type, Tuple, Union, Iterable

import networkx as nx

from depobs.database.models import (
    Advisory,
    PackageVersionID,
    PackageGraph,
    PackageReport,
    PackageVersion,
)
from depobs.scanner.graph_traversal import node_dep_ids_iter
import depobs.scanner.graph_util as graph_util


log = logging.getLogger(__name__)


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


class ScoreComponent:
    # a name to save the loaded data in the nx.DiGraph node attr
    graph_node_attr_name: Optional[str] = None

    # the PackageReport fields mapped to types get_package_report_updates returns
    package_report_fields: Dict[str, Any] = dict()

    # aggregates over nodes in graph mapped to types (e.g. score, total LOC, total vulns, unique
    # vulnerabilities w/ counts by severity, etc.)
    # get_node_aggregates
    aggregate_fields: Dict[str, Any] = dict()

    @staticmethod
    def data_by_package_version_id(
        db_graph: PackageGraph,
    ) -> Dict[PackageVersionID, Any]:
        """
        Returns a dict-like map from PackageVersion ID (also DiGraph
        node ID) to data for scoring this component.
        """
        raise NotImplementedError()

    @staticmethod
    def get_package_report_updates(
        component: Type["ScoreComponent"],
        g: nx.DiGraph,
        node_id: int,
        direct_dep_ids: Set[int],
        indirect_dep_ids: Set[int],
    ) -> Dict[str, Any]:
        """Computes fields from node with data, direct_deps, indirect_deps"""
        raise NotImplementedError()

    def get_node_aggregates(self, node: Dict) -> Dict[str, Any]:
        """
        TODO: Given a node returns values for aggregation? Computes
        fields from the node package report from data, direct_deps,
        indirect_deps, and additional data
        """
        raise NotImplementedError()


class PackageVersionScoreComponent(ScoreComponent):
    graph_node_attr_name = "package_version"

    package_report_fields = {
        "package": str,
        "version": str,
    }

    @staticmethod
    def data_by_package_version_id(
        db_graph: PackageGraph,
    ) -> Dict[PackageVersionID, Any]:
        return db_graph.distinct_package_versions_by_id

    @staticmethod
    def get_package_report_updates(
        component: Type["ScoreComponent"],
        g: nx.DiGraph,
        node_id: int,
        direct_dep_ids: Set[int],
        indirect_dep_ids: Set[int],
    ) -> Dict[str, str]:
        node_data = g.nodes[node_id].get(component.graph_node_attr_name, None)
        name = getattr(node_data, "name", None) if node_data else None
        version = getattr(node_data, "version", None) if node_data else None
        return dict(package=name, version=version,)


class NPMSIOScoreComponent(ScoreComponent):
    graph_node_attr_name = "npmsio_score"

    package_report_fields = {
        "npmsio_score": Union[None, float, int],
        "npmsio_scored_package_version": str,
    }

    @staticmethod
    def data_by_package_version_id(
        db_graph: PackageGraph,
    ) -> Dict[PackageVersionID, Any]:
        return db_graph.get_npmsio_scores_by_package_version_id()

    @staticmethod
    def get_package_report_updates(
        component: Type["ScoreComponent"],
        g: nx.DiGraph,
        node_id: int,
        direct_dep_ids: Set[int],
        indirect_dep_ids: Set[int],
    ) -> Dict[str, Union[None, float, int, str]]:
        package_version_and_scores: Optional[
            Tuple[str, Dict[str, Union[int, float, None]]]
        ] = g.nodes[node_id][component.graph_node_attr_name]
        if not (
            isinstance(package_version_and_scores, tuple)
            and len(package_version_and_scores) == 2
        ):
            return dict(npmsio_score=None, npmsio_scored_package_version=None,)

        package_version, scores = package_version_and_scores
        if not scores:
            return dict(npmsio_score=None, npmsio_scored_package_version=None,)

        if package_version in scores:  # this exact version was scored
            return dict(
                npmsio_score=scores[package_version],
                npmsio_scored_package_version=package_version,
            )
        # assuming semver versions find the longest common prefix
        scored_versions = sorted(scores.keys())
        closest_version = scored_versions[0]
        for scored_version in scored_versions:
            if len(commonprefix([package_version, scored_version])) > len(
                commonprefix([package_version, closest_version])
            ):
                closest_version = scored_version

        if closest_version:
            return dict(
                npmsio_score=scores[closest_version],
                npmsio_scored_package_version=closest_version,
            )
        return dict(npmsio_score=None, npmsio_scored_package_version=None,)


class NPMRegistryScoreComponent(ScoreComponent):
    graph_node_attr_name = "registry_entry"

    package_report_fields = {
        "release_date": Optional[datetime],
        "authors": Optional[int],
        "contributors": Optional[int],
    }

    @staticmethod
    def data_by_package_version_id(
        db_graph: PackageGraph,
    ) -> Dict[PackageVersionID, Any]:
        return db_graph.get_npm_registry_data_by_package_version_id()

    @staticmethod
    def get_package_report_updates(
        component: Type["ScoreComponent"],
        g: nx.DiGraph,
        node_id: int,
        direct_dep_ids: Set[int],
        indirect_dep_ids: Set[int],
    ) -> Dict[str, Union[None, int, datetime]]:
        node_data = g.nodes[node_id].get(component.graph_node_attr_name, None)
        published_at, maintainers, contributors = None, None, None
        if node_data:
            published_at, maintainers, contributors = node_data

        return dict(
            authors=(len(maintainers) if maintainers is not None else maintainers),
            contributors=(
                len(contributors) if contributors is not None else contributors
            ),
            release_date=published_at,
        )


class AdvisoryScoreComponent(ScoreComponent):
    graph_node_attr_name = "advisories"

    package_report_fields = {
        # directVulns{Critical,High,Medium,Low}_score are the number of
        # advisories of each severity directly affecting the package version
        **{
            f"directVulns{severity.name.capitalize()}_score": Optional[int]
            for severity in dict(zeroed_severity_counter()).keys()
        },
        # indirectVulns{Critical,High,Medium,Low}_score are the number of
        # advisories of each severity affecting direct and transitive
        # dependencies of the package version
        **{
            f"indirectVulns{severity.name.capitalize()}_score": Optional[int]
            for severity in dict(zeroed_severity_counter()).keys()
        },
    }

    @staticmethod
    def data_by_package_version_id(
        db_graph: PackageGraph,
    ) -> Dict[PackageVersionID, Any]:
        return db_graph.get_advisories_by_package_version_id()

    @staticmethod
    def get_package_report_updates(
        component: Type["ScoreComponent"],
        g: nx.DiGraph,
        node_id: int,
        direct_dep_ids: Set[int],
        indirect_dep_ids: Set[int],
    ) -> Dict[str, int]:
        result = {key: 0 for key in component.package_report_fields}

        node_advisories = g.nodes[node_id].get(component.graph_node_attr_name, []) or []
        direct_vuln_counts = count_advisories_by_severity(node_advisories)
        result.update(
            {
                f"directVulns{severity.name.capitalize()}_score": count
                for (severity, count) in dict(direct_vuln_counts).items()
            }
        )

        # TODO: de-dup by Advisory ID
        dep_advisory_lists: List[List[Advisory]] = [
            g.nodes[node_id].get(component.graph_node_attr_name, []) or []
            for node_id in (direct_dep_ids | indirect_dep_ids)
        ]
        dep_advisories = [
            advisory
            for dep_advisory_list in dep_advisory_lists
            for advisory in dep_advisory_list
        ]
        indirect_vuln_counts = count_advisories_by_severity(dep_advisories)
        result.update(
            {
                f"indirectVulns{severity.name.capitalize()}_score": count
                for (severity, count) in dict(indirect_vuln_counts).items()
            }
        )
        return result


class DependencyCountScoreComponent(ScoreComponent):
    graph_node_attr_name = None

    package_report_fields = {
        # number of unique reachable package-versions i.e. those reachable in the set and parents of the cycle
        "all_deps": int,
        # number of out edges / package constraints from .dependencies in a package.json file
        "immediate_deps": int,
    }

    @staticmethod
    def data_by_package_version_id(_: PackageGraph) -> Dict[PackageVersionID, Any]:
        return dict()

    @staticmethod
    def get_package_report_updates(
        component: Type["ScoreComponent"],
        g: nx.DiGraph,
        node_id: int,
        direct_dep_ids: Set[int],
        indirect_dep_ids: Set[int],
    ) -> Dict[str, int]:
        return dict(
            immediate_deps=len(direct_dep_ids),
            all_deps=len(direct_dep_ids | indirect_dep_ids),
        )


all_score_components = [
    PackageVersionScoreComponent,
    NPMSIOScoreComponent,
    NPMRegistryScoreComponent,
    AdvisoryScoreComponent,
    DependencyCountScoreComponent,
]


def score_package(
    g: nx.DiGraph,
    node_id: int,
    direct_dep_ids: Set[int],
    indirect_dep_ids: Set[int],
    score_components: Iterable[Type[ScoreComponent]],
) -> PackageReport:
    """Scores a package node on a PackageGraph using the provided components"""
    # get package report fields for each component
    report_kwargs = dict(scoring_date=datetime.now(), status="scanned",)
    for component in score_components:
        updates = component.get_package_report_updates(
            component,
            g=g,
            node_id=node_id,
            direct_dep_ids=direct_dep_ids,
            indirect_dep_ids=indirect_dep_ids,
        )

        report_kwargs.update(updates)
    return PackageReport(**report_kwargs)


def add_scoring_component_data_to_node_attrs(
    db_graph: PackageGraph,
    g: nx.DiGraph,
    score_components: Iterable[Type[ScoreComponent]],
) -> nx.DiGraph:
    """Adds node attribute data for the provided scoring components to the networkx package DiGraph in-place"""
    graph_util.update_node_attrs(
        g,
        **{
            **{
                component.graph_node_attr_name: component.data_by_package_version_id(
                    db_graph
                )
                for component in score_components
                if component.graph_node_attr_name is not None
                and component.graph_node_attr_name != ""
            },
            "label": {
                pv.id: f"{pv.name}@{pv.version}"
                for pv in db_graph.distinct_package_versions_by_id.values()
            },
        },
    )
    return g


def score_package_graph(
    db_graph: PackageGraph,
    score_components: Optional[Iterable[Type[ScoreComponent]]] = None,
    nx_graph: Optional[nx.DiGraph] = None,
) -> Dict[PackageVersionID, PackageReport]:
    """
    Scores a database PackageGraph model with the provided components.
    """
    # default to using all components if none are provided
    graph_score_components: Iterable[Type[ScoreComponent]] = []
    if score_components is None:
        graph_score_components = all_score_components
    else:
        graph_score_components = score_components
    assert graph_score_components is not None

    g: nx.DiGraph = add_scoring_component_data_to_node_attrs(
        db_graph,
        nx_graph or graph_util.package_graph_to_networkx_graph(db_graph),
        graph_score_components,
    )
    log.info(
        f"scoring graph id={db_graph.id} ({len(g.edges)} edges, {len(g.nodes)} nodes) with components {graph_score_components}"
    )
    direct_dep_ids_by_package_version_id: Dict[
        PackageVersionID, Set[PackageVersionID]
    ] = dict()
    reports_by_package_version_id: Dict[PackageVersionID, PackageReport] = dict()
    for node_id, direct_dep_ids, indirect_dep_ids in node_dep_ids_iter(g):
        direct_dep_ids_by_package_version_id[node_id] = direct_dep_ids
        reports_by_package_version_id[node_id] = score_package(
            g, node_id, direct_dep_ids, indirect_dep_ids, graph_score_components
        )

    # update report .dependencies relationship
    for node_id, direct_dep_ids in direct_dep_ids_by_package_version_id.items():
        reports_by_package_version_id[node_id].dependencies.extend(
            reports_by_package_version_id[dep_node_id] for dep_node_id in direct_dep_ids
        )

    return reports_by_package_version_id


def find_component_with_package_report_field(
    package_report_field: str,
) -> Optional[Type[ScoreComponent]]:
    for component in all_score_components:
        if package_report_field in component.package_report_fields.keys():
            return component
    return None
