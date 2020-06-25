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


def test_found_package_report_returns_200(models, client):
    delete_reports(models, "dep-obs-internal-wokka-wokka", "0.0.2")
    add_report(
        models,
        models.PackageReport(
            package="dep-obs-internal-wokka-wokka", version="0.0.2", scoring_date=None
        ),
    )

    response = client.get(
        "/package_report?package_name=dep-obs-internal-wokka-wokka&package_version=0.0.2"
    )
    assert response.status == "200 OK"


def test_missing_package_report_returns_404(client):
    delete_reports(models, "@hapi/bounceee", "0.0.2")
    response = client.get(
        "/package_report?package_name=%40hapi%2Fbounceee&package_version=0.0.2"
    )
    assert response.status == "404 NOT FOUND"
