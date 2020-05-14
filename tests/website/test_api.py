import pytest


def test_root_url_returns_index_page_title(client):
    response = client.get("/")
    assert response.status == "200 OK"


def test_missing_package_report_for_registered_package_name_and_version_initiates_scan(
    models, client
):
    # delete old reports for the scan we'll kick off
    for report in models.PackageReport.query.filter_by(
        package="@hapi/bounce", version="2.0.0",
    ):
        models.db.session.delete(report)
    models.db.session.commit()

    response = client.get(
        "/package?package_name=%40hapi%2Fbounce&package_version=2.0.0"
    )
    assert response.status == "202 ACCEPTED"
    assert response.json["status"] == "scanning"
    assert response.json["task_status"] == "PENDING"
