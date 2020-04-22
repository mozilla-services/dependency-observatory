# -*- coding: utf-8 -*-

import pytest

import depobs.worker.scoring as m


def test_score_package(mocker):
    # https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    dt_mock = mocker.patch("depobs.worker.scoring.datetime")

    npmsio_score_mock = mocker.patch("depobs.worker.scoring.get_npms_io_score")
    mocker.patch("depobs.worker.scoring.get_npm_registry_data")
    mocker.patch("depobs.worker.scoring.get_vulnerability_counts")
    scored: m.PackageReport = m.score_package(
        package_name="foo",
        package_version="0.0.0",
        direct_dep_reports=[],  # List[PackageReport]
        all_deps_count=0,
    )
    assert (
        scored.json_with_dependencies()
        == m.PackageReport(
            npmsio_score=npmsio_score_mock().first(),
            scoring_date=dt_mock.now(),
            package="foo",
            version="0.0.0",
            directVulnsCritical_score=0,
            directVulnsHigh_score=0,
            directVulnsMedium_score=0,
            directVulnsLow_score=0,
            all_deps=0,
            immediate_deps=0,
            indirectVulnsCritical_score=0,
            indirectVulnsHigh_score=0,
            indirectVulnsMedium_score=0,
            indirectVulnsLow_score=0,
            status="scanned",
        ).json_with_dependencies()
    )


def test_score_package_and_children():
    pass
