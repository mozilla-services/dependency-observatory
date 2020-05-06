# -*- coding: utf-8 -*-

from typing import Any, Dict, Iterator, Iterable, List, Optional, Tuple

import pytest

import depobs.worker.scoring as m


# NB: later values override:
# >>> {**{'x': 2}, 'x': 1}
# {'x': 1}
#
_default_report_advisories = {
    "directVulnsCritical_score": 0,
    "directVulnsHigh_score": 0,
    "directVulnsLow_score": 0,
    "directVulnsMedium_score": 0,
    "indirectVulnsCritical_score": 0,
    "indirectVulnsHigh_score": 0,
    "indirectVulnsLow_score": 0,
    "indirectVulnsMedium_score": 0,
}

_default_report_json = {
    **_default_report_advisories,
    "id": None,
    "task_id": None,
    "task_status": None,
    "authors": None,
    "contributors": None,
    "all_deps": 0,
    "dependencies": [],
    "immediate_deps": 0,
    "npmsio_score": 0,
    "release_date": None,
    "status": "scanned",
    "top_score": None,
}


def test_score_package_component_fails_for_empty_graph():
    with pytest.raises(KeyError):
        assert m.score_package(
            m.nx.empty_graph(n=0, create_using=m.nx.DiGraph),
            0,
            set(),
            set(),
            [m.PackageVersionScoreComponent],
        )


def test_score_package_component_fails_for_node_id_not_in_graph():
    with pytest.raises(KeyError):
        assert m.score_package(
            create_single_node_digraph_with_attrs({"package_version": None}),
            99,
            set(),
            set(),
            [m.PackageVersionScoreComponent],
        )


def create_single_node_digraph_with_attrs(attrs: Dict) -> m.nx.DiGraph:
    return create_digraph([(0, attrs)])


def create_digraph(
    nodes: Iterable[Tuple[int, Dict]], edges: Iterable[Tuple[int, int]] = None,
) -> m.nx.DiGraph:
    if edges is None:
        edges = []
    g = m.nx.DiGraph()
    for node_id, node_attrs in nodes:
        g.add_node(node_id, **node_attrs)
    g.add_edges_from(edges)
    return g


score_package_component_testcases = {
    "no_components": [
        create_single_node_digraph_with_attrs({}),
        0,
        [],
        {"status": "scanned", "scoring_date": "replace_with_mocked_value",},
    ],
    "null_package_version": [
        create_single_node_digraph_with_attrs({"package_version": None}),
        0,
        [m.PackageVersionScoreComponent],
        {"package": None, "version": None},
    ],
    "empty_package_version": [
        create_single_node_digraph_with_attrs({"package_version": m.PackageVersion()}),
        0,
        [m.PackageVersionScoreComponent],
        {"package": None, "version": None},
    ],
    "package_version": [
        create_single_node_digraph_with_attrs(
            {"package_version": m.PackageVersion(**{"name": "foo", "version": "0.0.0"})}
        ),
        0,
        [m.PackageVersionScoreComponent],
        {"package": "foo", "version": "0.0.0"},
    ],
    "null_npmsio_score": [
        create_single_node_digraph_with_attrs({"npmsio_score": None}),
        0,
        [m.NPMSIOScoreComponent],
        {"npmsio_score": None},
    ],
    "npmsio_score_zero": [
        create_single_node_digraph_with_attrs({"npmsio_score": 0}),
        0,
        [m.NPMSIOScoreComponent],
        {"npmsio_score": 0.0,},
    ],
    "npmsio_score_halfish": [
        create_single_node_digraph_with_attrs({"npmsio_score": 0.53}),
        0,
        [m.NPMSIOScoreComponent],
        {"npmsio_score": 0.53,},
    ],
    "npmsio_score_one": [
        create_single_node_digraph_with_attrs({"npmsio_score": 1}),
        0,
        [m.NPMSIOScoreComponent],
        {"npmsio_score": 1.0,},
    ],
    "null_npm_reg": [
        create_single_node_digraph_with_attrs({"registry_entry": None}),
        0,
        [m.NPMRegistryScoreComponent],
        {"release_date": None,},
    ],
    "npm_reg_null_published_at": [
        create_single_node_digraph_with_attrs(
            # published_at, maintainers, contributors as returned by models.get_npm_registry_data
            {"registry_entry": (None, None, None)}
        ),
        0,
        [m.NPMRegistryScoreComponent],
        {"release_date": None,},
    ],
    "npm_reg_published_at": [
        create_single_node_digraph_with_attrs(
            # published_at, maintainers, contributors as returned by models.get_npm_registry_data
            {"registry_entry": (m.datetime(year=2030, month=1, day=1), None, None)}
        ),
        0,
        [m.NPMRegistryScoreComponent],
        {"release_date": m.datetime(year=2030, month=1, day=1),},
    ],
    "npm_reg_null_contributors": [
        create_single_node_digraph_with_attrs(
            # published_at, maintainers, contributors as returned by models.get_npm_registry_data
            {"registry_entry": (None, None, None)}
        ),
        0,
        [m.NPMRegistryScoreComponent],
        {"contributors": None,},
    ],
    "npm_reg_empty_contributors": [
        # published_at, maintainers, contributors as returned by models.get_npm_registry_data
        create_single_node_digraph_with_attrs({"registry_entry": (None, None, [])}),
        0,
        [m.NPMRegistryScoreComponent],
        {"contributors": 0,},
    ],
    "npm_reg_two_contributors": [
        # published_at, maintainers, contributors as returned by models.get_npm_registry_data
        create_single_node_digraph_with_attrs(
            {
                "registry_entry": (
                    None,
                    None,
                    ["contributor1@example.com", "contributor2@example.com",],
                )
            }
        ),
        0,
        [m.NPMRegistryScoreComponent],
        {"contributors": 2,},
    ],
    "npm_reg_null_maintainers": [
        # published_at, maintainers, contributors as returned by models.get_npm_registry_data
        create_single_node_digraph_with_attrs({"registry_entry": (None, None, None)}),
        0,
        [m.NPMRegistryScoreComponent],
        {"authors": None,},
    ],
    "npm_reg_empty_maintainers": [
        # published_at, maintainers, contributors as returned by models.get_npm_registry_data
        create_single_node_digraph_with_attrs({"registry_entry": (None, [], None)}),
        0,
        [m.NPMRegistryScoreComponent],
        {"authors": 0,},
    ],
    "npm_reg_two_maintainers": [
        # published_at, maintainers, contributors as returned by models.get_npm_registry_data
        create_single_node_digraph_with_attrs(
            {
                "registry_entry": (
                    None,
                    ["contributor1@example.com", "contributor2@example.com",],
                    None,
                )
            }
        ),
        0,
        [m.NPMRegistryScoreComponent],
        {"authors": 2,},
    ],
    "null_advisories": [
        create_single_node_digraph_with_attrs({"advisories": None}),
        0,
        [m.AdvisoryScoreComponent],
        _default_report_advisories,
    ],
    "empty_advisories": [
        create_single_node_digraph_with_attrs({"advisories": []}),
        0,
        [m.AdvisoryScoreComponent],
        _default_report_advisories,
    ],
    "advisories_direct": [
        create_single_node_digraph_with_attrs(
            {
                "advisories": [
                    m.Advisory(severity="critical"),
                    m.Advisory(severity="high"),
                    m.Advisory(severity="medium"),
                    # should count moderate as medium
                    m.Advisory(severity="moderate"),
                    m.Advisory(severity="low"),
                    m.Advisory(severity="unexpected"),
                ]
            }
        ),
        0,
        [m.AdvisoryScoreComponent],
        {
            **_default_report_advisories,
            "directVulnsCritical_score": 1,
            "directVulnsHigh_score": 1,
            "directVulnsLow_score": 1,
            "directVulnsMedium_score": 2,
        },
    ],
    "advisories_indirect": [
        create_digraph(
            nodes=[
                (0, {"advisories": []}),
                (
                    1,
                    {
                        "advisories": [
                            m.Advisory(severity="moderate"),
                            m.Advisory(severity="high"),
                        ]
                    },
                ),
                (
                    2,
                    {
                        "advisories": [
                            m.Advisory(severity="critical"),
                            m.Advisory(severity="low"),
                            m.Advisory(severity="medium"),
                            m.Advisory(severity="unexpected"),
                        ]
                    },
                ),
                (3, {"advisories": []}),
            ],
            edges=[(0, 1), (1, 2), (0, 3)],
        ),
        0,
        [m.AdvisoryScoreComponent],
        {
            **_default_report_advisories,
            "indirectVulnsCritical_score": 1,
            "indirectVulnsHigh_score": 1,
            "indirectVulnsLow_score": 1,
            "indirectVulnsMedium_score": 2,
        },
    ],
    "no_deps": [
        create_digraph([(0, {})]),
        0,
        [m.DependencyCountScoreComponent],
        {"all_deps": 0, "immediate_deps": 0,},
    ],
    "three_immediate_deps": [
        create_digraph(
            nodes=[(0, {}), (1, {}), (2, {}), (3, {}),], edges=[(0, 1), (0, 2), (0, 3),]
        ),
        0,
        [m.DependencyCountScoreComponent],
        {"all_deps": 3, "immediate_deps": 3,},
    ],
    "one_immediate_three_transitive_deps": [
        create_digraph(
            nodes=[(0, {}), (1, {}), (2, {}), (3, {}), (4, {}),],
            edges=[(0, 1), (1, 2), (1, 3), (1, 4),],
        ),
        0,
        [m.DependencyCountScoreComponent],
        {"all_deps": 4, "immediate_deps": 1,},
    ],
}


@pytest.mark.parametrize(
    "g, node_id, score_components, expected_fields",
    score_package_component_testcases.values(),
    ids=score_package_component_testcases.keys(),
)
def test_score_package_component(
    g: m.nx.DiGraph,
    node_id: int,
    score_components: Iterable[m.ScoreComponent],
    expected_fields: Dict[str, Any],
    mocker,
):
    # https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    dt_mock = mocker.patch("depobs.worker.scoring.datetime")
    if "scoring_date" in expected_fields:
        expected_fields["scoring_date"] = dt_mock.now()

    report: m.PackageReport = m.score_package(
        g,
        node_id,
        set(g.successors(node_id)),
        set(list(m.nx.algorithms.dag.descendants(g, node_id)))
        - set(g.successors(node_id)),
        score_components,
    )

    for key, expected_value in expected_fields.items():
        assert hasattr(report, key)
        assert (
            getattr(report, key) == expected_fields[key]
        ), f"report {key} value {getattr(report, key)!r} did not match expected value {expected_fields[key]!r}"


score_package_graph_testcases = {
    # NB: digraph node IDs need to match PackageVersion ids
    "one_node_no_edges": (
        m.PackageGraph(
            id=-1,
            package_links_by_id={0: (0, 0)},
            distinct_package_versions_by_id={
                0: m.PackageVersion(id=0, name="test-solo-pkg", version="0.1.0"),
            },
            get_npmsio_scores_by_package_version_id=lambda: {0: 0.0},
            get_npm_registry_data_by_package_version_id=lambda: {0: None},
            get_advisories_by_package_version_id=lambda: {0: []},
        ),
        [
            m.PackageReport(
                package="test-solo-pkg",
                version="0.1.0",
                status="scanned",
                all_deps=0,
                directVulnsCritical_score=0,
                directVulnsHigh_score=0,
                directVulnsLow_score=0,
                directVulnsMedium_score=0,
                immediate_deps=0,
                indirectVulnsCritical_score=0,
                indirectVulnsHigh_score=0,
                indirectVulnsLow_score=0,
                indirectVulnsMedium_score=0,
                npmsio_score=0.0,
            ).json_with_dependencies(depth=0)
        ],
    ),
    "three_node_path_graph": (
        m.PackageGraph(
            id=-1,
            # m.nx.path_graph(3, create_using=m.nx.DiGraph),
            package_links_by_id={0: (0, 1), 1: (1, 2)},
            distinct_package_versions_by_id={
                0: m.PackageVersion(id=0, name="test-root-pkg", version="0.1.0"),
                1: m.PackageVersion(id=1, name="test-child-pkg", version="0.0.3"),
                2: m.PackageVersion(id=2, name="test-grandchild-pkg", version="2.1.0"),
            },
            get_npmsio_scores_by_package_version_id=lambda: {0: 0.34, 1: 0.9, 2: 0.25},
            get_npm_registry_data_by_package_version_id=lambda: {
                0: None,
                1: None,
                2: None,
            },
            get_advisories_by_package_version_id=lambda: {0: [], 1: [], 2: []},
        ),
        [
            {
                **_default_report_json,
                "npmsio_score": 0.25,
                "package": "test-grandchild-pkg",
                "version": "2.1.0",
            },
            {
                **_default_report_json,
                "all_deps": 1,
                "dependencies": [
                    {
                        **_default_report_json,
                        "npmsio_score": 0.25,
                        "package": "test-grandchild-pkg",
                        "version": "2.1.0",
                    },
                ],
                "immediate_deps": 1,
                "npmsio_score": 0.9,
                "package": "test-child-pkg",
                "version": "0.0.3",
            },
            {
                **_default_report_json,
                "all_deps": 2,
                "authors": None,
                "dependencies": [
                    {
                        **_default_report_json,
                        "all_deps": 1,
                        "immediate_deps": 1,
                        "npmsio_score": 0.9,
                        "package": "test-child-pkg",
                        "version": "0.0.3",
                    },
                ],
                "immediate_deps": 1,
                "npmsio_score": 0.34,
                "package": "test-root-pkg",
                "version": "0.1.0",
            },
        ],
    ),
    "two_node_loop": (
        m.PackageGraph(
            id=-1,
            package_links_by_id={0: (0, 1), 1: (1, 0),},
            distinct_package_versions_by_id={
                0: m.PackageVersion(id=0, name="test-root-pkg", version="0.1.0"),
                1: m.PackageVersion(id=1, name="test-child-pkg", version="0.0.3"),
            },
            get_npmsio_scores_by_package_version_id=lambda: {0: 0.2, 1: 0.8,},
            get_npm_registry_data_by_package_version_id=lambda: {0: None, 1: None},
            get_advisories_by_package_version_id=lambda: {0: [], 1: [],},
        ),
        [
            {
                **_default_report_json,
                "all_deps": 1,
                "immediate_deps": 1,
                "npmsio_score": 0.8,
                "package": "test-child-pkg",
                "version": "0.0.3",
                "dependencies": [
                    {
                        **_default_report_json,
                        "all_deps": 1,
                        "immediate_deps": 1,
                        "npmsio_score": 0.2,
                        "package": "test-root-pkg",
                        "version": "0.1.0",
                    }
                ],
            },
            {
                **_default_report_json,
                "all_deps": 1,
                "immediate_deps": 1,
                "npmsio_score": 0.2,
                "package": "test-root-pkg",
                "version": "0.1.0",
                "dependencies": [
                    {
                        **_default_report_json,
                        "all_deps": 1,
                        "immediate_deps": 1,
                        "npmsio_score": 0.8,
                        "package": "test-child-pkg",
                        "version": "0.0.3",
                    }
                ],
            },
        ],
    ),
}


@pytest.mark.parametrize(
    "db_graph, expected_package_reports_with_deps_json",
    score_package_graph_testcases.values(),
    ids=score_package_graph_testcases.keys(),
)
def test_score_package_graph(
    db_graph: m.PackageGraph,
    expected_package_reports_with_deps_json: List[Dict[str, Any]],
    mocker,
):
    dt_mock = mocker.patch("depobs.worker.scoring.datetime")
    for r in expected_package_reports_with_deps_json:
        r["scoring_date"] = dt_mock.now()
        for dep in r.get("dependencies", []):
            dep["scoring_date"] = dt_mock.now()

    reports = m.score_package_graph(db_graph)

    # one report per node
    assert (
        len(db_graph.distinct_package_ids)
        == len(reports)
        == len(expected_package_reports_with_deps_json)
    )

    # should have correct direct and indirect dep counts
    for report, expected_report_json in zip(
        reports, expected_package_reports_with_deps_json
    ):
        assert report.json_with_dependencies() == expected_report_json


count_advisories_by_severity_testcases = {
    "none": ([], m.Counter()),
    "empty_str_ignored": ([m.Advisory(severity=""),], m.Counter(),),
    "none_ignored": ([m.Advisory(severity=None),], m.Counter(),),
    "one_critical_upper_case_counted": (
        [m.Advisory(severity="CRITICAL")],
        m.Counter({m.AdvisorySeverity.CRITICAL: 1}),
    ),
    "one_critical_mixed_case_counted": (
        [m.Advisory(severity="cRitiCal")],
        m.Counter({m.AdvisorySeverity.CRITICAL: 1}),
    ),
    "one_medium_one_moderate_counted": (
        [m.Advisory(severity="medium"), m.Advisory(severity="moderate")],
        m.Counter({m.AdvisorySeverity.MEDIUM: 2}),
    ),
    "one_critical_counted": (
        [m.Advisory(severity="critical")],
        m.Counter({m.AdvisorySeverity.CRITICAL: 1}),
    ),
    "two_critical_counted": (
        [m.Advisory(severity="critical"), m.Advisory(severity="critical")],
        m.Counter({m.AdvisorySeverity.CRITICAL: 2}),
    ),
    "two_critical_one_high_counted": (
        [
            m.Advisory(severity="critical"),
            m.Advisory(severity="critical"),
            m.Advisory(severity="high"),
        ],
        m.Counter({m.AdvisorySeverity.CRITICAL: 2, m.AdvisorySeverity.HIGH: 1}),
    ),
}


@pytest.mark.parametrize(
    "advisories, expected_counter",
    count_advisories_by_severity_testcases.values(),
    ids=count_advisories_by_severity_testcases.keys(),
)
def test_count_advisories_by_severity(
    advisories: List[m.Advisory], expected_counter: m.Counter
):
    assert m.count_advisories_by_severity(advisories) == expected_counter


def test_zeroed_severity_counter():
    zeroed = m.zeroed_severity_counter()
    for severity in m.AdvisorySeverity:
        assert zeroed[severity] == 0
    assert len(zeroed) == len(m.AdvisorySeverity)
