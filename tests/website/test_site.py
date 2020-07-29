import datetime

import pytest


@pytest.mark.unit
def test_root_url_returns_index_page_title(client):
    response = client.get("/")
    assert response.status == "200 OK"


@pytest.mark.unit
def test_invalid_package_report_params(client):
    # missing package manager
    response = client.get(
        "/package_report?package_name=dep-obs-internal-wokka-wokka&package_version=0.0.2"
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"package_manager": ["Missing data for required field."]}

    # invalid package manager
    response = client.get(
        "/package_report?package_name=dep-obs-internal-wokka-wokka&package_version=0.0.2&package_manager=npms"
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"package_manager": ["Must be equal to npm."]}

    # missing package name
    response = client.get("/package_report?package_version=0.0.2&package_manager=npm")
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"package_name": ["Missing data for required field."]}

    # invalid package name
    response = client.get(
        "/package_report?package_name=../dep-obs-internal-wokka-wokka&package_version=0.0.2&package_manager=npm"
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {
        "package_name": ["String does not match expected pattern."]
    }

    # invalid package version (NB: missing package version OK)
    response = client.get(
        "/package_report?package_name=dep-obs-internal-wokka-wokka&package_version=&package_manager=npm"
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {
        "package_version": ["String does not match expected pattern."]
    }


def add_report(models, report):
    models.db.session.add(report)
    models.db.session.commit()


def delete_reports(models, package_name, package_version):
    for report in models.PackageReport.query.filter_by(
        package=package_name, version=package_version,
    ):
        models.db.session.delete(report)
    models.db.session.commit()


def test_found_package_report_returns_200(models, client):
    delete_reports(models, "dep-obs-internal-wokka-wokka", "0.0.2")
    add_report(
        models,
        models.PackageReport(
            package="dep-obs-internal-wokka-wokka", version="0.0.2", scoring_date=datetime.datetime.now(),
        ),
    )

    response = client.get(
        "/package_report?package_name=dep-obs-internal-wokka-wokka&package_version=0.0.2&package_manager=npm"
    )
    assert response.status == "200 OK"


def test_missing_package_report_returns_404(models, client):
    delete_reports(models, "@hapi/bounceee", "0.0.2")
    response = client.get(
        "/package_report?package_name=%40hapi%2Fbounceee&package_version=0.0.2&package_manager=npm"
    )
    assert response.status == "404 NOT FOUND"


def test_scan_logs_returns_200(models, client):
    scan_response = client.post(
        "/api/v1/scans",
        json={
            "name": "scan_score_npm_package",
            "args": ["temp-package", "temp-package-version"],
            "kwargs": {},
        },
    )
    assert scan_response.status == "202 ACCEPTED"
    scan_id = scan_response.json["id"]

    response = client.get(f"/scans/{scan_id}/logs",)
    assert response.status == "200 OK"
