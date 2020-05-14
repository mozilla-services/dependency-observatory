import pytest


def test_root_url_returns_index_page_title(client):
    response = client.get("/")
    assert response.status == "200 OK"


def add_report(models, report):
    models.db.session.add(report)
    models.db.session.commit()


def delete_reports(models, package_name, package_version):
    for report in models.PackageReport.query.filter_by(
        package=package_name, version=package_version,
    ):
        models.db.session.delete(report)
    models.db.session.commit()


def test_found_package_report_with_error_status_returns_500(models, client):
    delete_reports(models, "dep-obs-internal-wokka-wokka", "0.0.1")
    add_report(
        models,
        models.PackageReport(
            package="dep-obs-internal-wokka-wokka", version="0.0.1", status="error"
        ),
    )

    response = client.get(
        "/package?package_name=dep-obs-internal-wokka-wokka&package_version=0.0.1"
    )
    assert response.status == "500 INTERNAL SERVER ERROR"


def test_found_package_report_without_score_returns_202(models, client):
    delete_reports(models, "dep-obs-internal-wokka-wokka", "0.0.2")
    add_report(
        models,
        models.PackageReport(
            package="dep-obs-internal-wokka-wokka", version="0.0.2", scoring_date=None
        ),
    )

    response = client.get(
        "/package?package_name=dep-obs-internal-wokka-wokka&package_version=0.0.2"
    )
    assert response.status == "202 ACCEPTED"


def test_missing_package_report_for_unregistered_package_name_404s(client):
    response = client.get("/package?package_name=%40hapi%2Fbounceee")
    assert response.status == "404 NOT FOUND"


def test_missing_package_report_for_unregistered_package_name_and_version_404s(client):
    response = client.get(
        "/package?package_name=%40hapi%2Fbounceee&package_version=0.0.0"
    )
    assert response.status == "404 NOT FOUND"


def test_missing_package_report_for_registered_package_name_and_missing_version_404s(
    client,
):
    response = client.get(
        "/package?package_name=%40hapi%2Fbounce&package_version=0.0.0"
    )
    assert response.status == "404 NOT FOUND"


def test_missing_package_report_for_registered_package_name_and_version_initiates_scan(
    models, client
):
    # delete old reports for the scan we'll kick off
    delete_reports(models, "@hapi/bounce", "2.0.0")

    response = client.get(
        "/package?package_name=%40hapi%2Fbounce&package_version=2.0.0"
    )
    assert response.status == "202 ACCEPTED"
    assert response.json["status"] == "scanning"
    assert response.json["task_status"] == "PENDING"


def test_missing_package_report_for_registered_package_name_initiates_scans_for_all_versions(
    models, client
):
    response = client.get("/package?package_name=%40hapi%2Fbounce")
    assert response.status == "202 ACCEPTED"
    # NB: v2.0.0 might have completed so we aren't checking its status
    response = client.get(
        "/package?package_name=%40hapi%2Fbounce&package_version=1.3.0"
    )
    assert response.status == "202 ACCEPTED"
    response = client.get(
        "/package?package_name=%40hapi%2Fbounce&package_version=1.3.1"
    )
    assert response.status == "202 ACCEPTED"
