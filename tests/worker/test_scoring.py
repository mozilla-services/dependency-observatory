# -*- coding: utf-8 -*-

from typing import Any, Dict, Iterator, List, Optional, Tuple

import pytest

import depobs.worker.scoring as m


# NB: later values override:
# >>> {**{'x': 2}, 'x': 1}
# {'x': 1}
#
_default_report_json = {
    "directVulnsCritical_score": 0,
    "directVulnsHigh_score": 0,
    "directVulnsLow_score": 0,
    "directVulnsMedium_score": 0,
    "indirectVulnsCritical_score": 0,
    "indirectVulnsHigh_score": 0,
    "indirectVulnsLow_score": 0,
    "indirectVulnsMedium_score": 0,
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


score_package_testcases = {
    "zero_npmsio_score": (
        [],
        None,
        0,
        m.PackageVersion(name="foo", version="0.0.0"),
        [],
        {**_default_report_json, "package": "foo", "version": "0.0.0",},
    ),
    "nonzero_npmsio_score": (
        [],
        None,
        0.53,
        m.PackageVersion(name="foo", version="0.0.0"),
        [],
        {
            **_default_report_json,
            "npmsio_score": 0.53,
            "package": "foo",
            "version": "0.0.0",
        },
    ),
    "nonzero_npmsio_score_direct_advisories": (
        [
            m.Advisory(severity="critical"),
            m.Advisory(severity="high"),
            m.Advisory(severity="medium"),
            m.Advisory(severity="moderate"),
            m.Advisory(severity="low"),
            m.Advisory(severity="unexpected"),
        ],
        None,
        0.53,
        m.PackageVersion(name="foo", version="0.0.0"),
        [],
        {
            **_default_report_json,
            "directVulnsCritical_score": 1,
            "directVulnsHigh_score": 1,
            "directVulnsLow_score": 1,
            "directVulnsMedium_score": 2,
            "npmsio_score": 0.53,
            "package": "foo",
            "version": "0.0.0",
        },
    ),
    "nonzero_npmsio_score_null_npm_reg_data": (
        [],
        (None, None, None),
        0.53,
        m.PackageVersion(name="foo", version="0.0.0"),
        [],
        {
            **_default_report_json,
            "authors": 0,
            "contributors": 0,
            "npmsio_score": 0.53,
            "package": "foo",
            "version": "0.0.0",
        },
    ),
    "nonzero_npmsio_score_npm_reg_data": (
        [],
        (
            "release day!",
            ["author1@example.com"],
            ["contributor1@example.com", "contributor2@example.com"],
        ),
        0.53,
        m.PackageVersion(name="foo", version="0.0.0"),
        [],
        {
            **_default_report_json,
            "authors": 1,
            "contributors": 2,
            "npmsio_score": 0.53,
            "release_date": "release day!",
            "package": "foo",
            "version": "0.0.0",
        },
    ),
    "nonzero_npmsio_score_direct_dep_reports": (
        [],
        (
            "release day!",
            ["author1@example.com"],
            ["contributor1@example.com", "contributor2@example.com"],
        ),
        0.53,
        m.PackageVersion(name="foo", version="0.0.0"),
        [
            m.PackageReport(
                directVulnsCritical_score=None,
                directVulnsHigh_score=None,
                directVulnsMedium_score=None,
                directVulnsLow_score=None,
                indirectVulnsCritical_score=None,
                indirectVulnsHigh_score=None,
                indirectVulnsMedium_score=None,
                indirectVulnsLow_score=None,
            ),
            m.PackageReport(
                directVulnsCritical_score=2,
                directVulnsHigh_score=None,
                directVulnsMedium_score=None,
                directVulnsLow_score=None,
                indirectVulnsCritical_score=None,
                indirectVulnsHigh_score=1,
                indirectVulnsMedium_score=None,
                indirectVulnsLow_score=None,
            ),
            m.PackageReport(
                directVulnsCritical_score=1,
                directVulnsHigh_score=None,
                directVulnsMedium_score=None,
                directVulnsLow_score=None,
                indirectVulnsCritical_score=None,
                indirectVulnsHigh_score=1,
                indirectVulnsMedium_score=1,
                indirectVulnsLow_score=1,
            ),
        ],
        {
            **_default_report_json,
            "authors": 1,
            "contributors": 2,
            "dependencies": [
                m.PackageReport(
                    directVulnsCritical_score=None,
                    directVulnsHigh_score=None,
                    directVulnsMedium_score=None,
                    directVulnsLow_score=None,
                    indirectVulnsCritical_score=None,
                    indirectVulnsHigh_score=None,
                    indirectVulnsMedium_score=None,
                    indirectVulnsLow_score=None,
                ).json_with_dependencies(depth=0),
                m.PackageReport(
                    directVulnsCritical_score=2,
                    directVulnsHigh_score=None,
                    directVulnsMedium_score=None,
                    directVulnsLow_score=None,
                    indirectVulnsCritical_score=None,
                    indirectVulnsHigh_score=1,
                    indirectVulnsMedium_score=None,
                    indirectVulnsLow_score=None,
                ).json_with_dependencies(depth=0),
                m.PackageReport(
                    directVulnsCritical_score=1,
                    directVulnsHigh_score=None,
                    directVulnsMedium_score=None,
                    directVulnsLow_score=None,
                    indirectVulnsCritical_score=None,
                    indirectVulnsHigh_score=1,
                    indirectVulnsMedium_score=1,
                    indirectVulnsLow_score=1,
                ).json_with_dependencies(depth=0),
            ],
            "immediate_deps": 3,
            "indirectVulnsCritical_score": 3,
            "indirectVulnsHigh_score": 2,
            "indirectVulnsLow_score": 1,
            "indirectVulnsMedium_score": 1,
            "npmsio_score": 0.53,
            "release_date": "release day!",
            "package": "foo",
            "version": "0.0.0",
        },
    ),
}


@pytest.mark.parametrize(
    "advisories, npm_registry_data, npmsio_score, package_version, direct_dep_reports, expected_package_report_with_deps_json",
    score_package_testcases.values(),
    ids=score_package_testcases.keys(),
)
def test_score_package(
    mocker,
    advisories: Iterator[m.Advisory],
    npm_registry_data: Optional[
        Tuple[Any, List[str], List[str]]
    ],  # published_at, maintainers, contributors
    npmsio_score: Optional[int],
    package_version: Optional[m.PackageVersion],
    direct_dep_reports: List[m.PackageReport],
    expected_package_report_with_deps_json: Dict[str, Any],
):
    # https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    dt_mock = mocker.patch("depobs.worker.scoring.datetime")
    expected_package_report_with_deps_json["scoring_date"] = dt_mock.now()

    npmsio_score_mock = mocker.patch(
        "depobs.worker.scoring.get_npms_io_score",
        **{"return_value.first.return_value": npmsio_score},
    )
    mocker.patch(
        "depobs.worker.scoring.get_npm_registry_data",
        **{"return_value.one_or_none.return_value": npm_registry_data},
    )
    mocker.patch(
        "depobs.worker.scoring.get_advisories_by_package_versions",
        return_value=advisories,
    )
    mocker.patch(
        "depobs.worker.scoring.get_package_from_name_and_version",
        return_value=package_version,
    )

    scored: m.PackageReport = m.score_package(
        package_name="foo",
        package_version="0.0.0",
        direct_dep_reports=direct_dep_reports,
        all_deps_count=0,
    )
    assert scored
    assert len(scored.dependencies) == len(
        expected_package_report_with_deps_json["dependencies"]
    )
    assert scored.json_with_dependencies() == expected_package_report_with_deps_json


score_package_and_children_testcases = {
    # NB: digraph node IDs need to match PackageVersion ids
    "one_node_no_edges": (
        [[]],
        [None],
        [0.0],
        m.nx.trivial_graph(create_using=m.nx.DiGraph),
        {0: m.PackageVersion(id=0, name="test-solo-pkg", version="0.1.0")},
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
        [[], [], []],
        [None, None, None],
        [0.25, 0.9, 0.34],
        m.nx.path_graph(3, create_using=m.nx.DiGraph),
        {
            0: m.PackageVersion(id=0, name="test-root-pkg", version="0.1.0"),
            1: m.PackageVersion(id=1, name="test-child-pkg", version="0.0.3"),
            2: m.PackageVersion(id=2, name="test-grandchild-pkg", version="2.1.0"),
        },
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
}


@pytest.mark.parametrize(
    "advisories, npm_registry_data, npmsio_scores, graph, package_versions, expected_package_reports_with_deps_json",
    score_package_and_children_testcases.values(),
    ids=score_package_and_children_testcases.keys(),
)
def test_score_package_and_children(
    mocker,
    # mocked calls
    advisories: List[Iterator[m.Advisory]],
    npm_registry_data: List[
        Iterator[Tuple[Any, List[str], List[str]]]
    ],  # generates: published_at, maintainers, contributors
    npmsio_scores: List[Optional[int]],
    # args
    graph: m.nx.DiGraph,
    package_versions: Dict[int, m.PackageVersion],
    expected_package_reports_with_deps_json: List[Dict[str, Any]],
):
    dt_mock = mocker.patch("depobs.worker.scoring.datetime")

    for r in expected_package_reports_with_deps_json:
        r["scoring_date"] = dt_mock.now()
        for r_dep in r["dependencies"]:
            r_dep["scoring_date"] = dt_mock.now()

    npmsio_score_mock = mocker.patch(
        "depobs.worker.scoring.get_npms_io_score",
        **{"return_value.first.side_effect": npmsio_scores},
    )
    mocker.patch(
        "depobs.worker.scoring.get_npm_registry_data",
        **{"return_value.one_or_none.side_effect": npm_registry_data},
    )
    mocker.patch(
        "depobs.worker.scoring.get_advisories_by_package_versions",
        side_effect=advisories,
    )
    mocker.patch(
        "depobs.worker.scoring.get_package_from_name_and_version",
        side_effect=package_versions,
    )

    reports = m.score_package_and_children(graph, package_versions)

    # one report per node
    assert (
        len(graph.nodes)
        == len(package_versions)
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
