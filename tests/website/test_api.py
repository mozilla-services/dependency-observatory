import pytest


@pytest.mark.unit
def test_invalid_create_scan_params(client):
    response = client.post("/api/v1/scans",)
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"_schema": ["Invalid input type."]}

    # missing name
    response = client.post("/api/v1/scans", json={},)
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {
        "package_manager": ["Missing data for required field."],
        "package_name": ["Missing data for required field."],
        "package_versions_type": ["Missing data for required field."],
        "scan_type": ["Missing data for required field."],
    }

    # invalid scan_type
    response = client.post(
        "/api/v1/scans",
        json={
            "scan_type": "foo",
            "package_name": "test",
            "package_manager": "npm",
            "package_versions_type": "releases",
        },
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"scan_type": ["Must be equal to scan_score_npm_package."]}

    response = client.post(
        "/api/v1/scans",
        json={
            "scan_type": "scan_score_npm_package",
            "package_name": "test",
            "package_manager": "npm",
            "package_versions_type": "releases",
            "extra": -1,
        },
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"extra": ["Unknown field."]}


def delete_scan_results(models, scan_id: int):
    # delete any stray results
    [models.db.session.delete(scan) for scan in models.get_scan_results_by_id(scan_id)]
    models.db.session.commit()


def test_valid_create_job_and_get(models, client, valid_scan_payload):
    scan_response = client.post("/api/v1/scans", json=valid_scan_payload,)
    assert scan_response.status == "202 ACCEPTED"
    assert "id" in scan_response.json
    scan_id = scan_response.json["id"]

    response = client.get(f"/api/v1/scans/{scan_id}",)
    assert response.status == "200 OK"

    delete_scan_results(models, scan_id)
    response = client.get(f"/api/v1/scans/{scan_id}/logs",)
    assert response.status == "404 NOT FOUND"

    # insert fake scan results
    results = [
        models.JSONResult(
            data={"attributes": {"SCAN_ID": scan_id}, "data": [{"foo": 0.5}]},
        ),
        models.JSONResult(
            data={
                "attributes": {"SCAN_ID": scan_id},
                "data": [{"spam": "cheese"}, {"line": 2}],
            },
        ),
    ]
    models.db.session.add_all(results)
    models.db.session.commit()

    response = client.get(f"/api/v1/scans/{scan_id}/logs",)
    assert response.status == "200 OK"
    assert response.json == [
        {
            "id": results[0].id,
            "data": {"data": [{"foo": 0.5}], "attributes": {"SCAN_ID": scan_id}},
        },
        {
            "id": results[1].id,
            "data": {
                "data": [{"spam": "cheese"}, {"line": 2}],
                "attributes": {"SCAN_ID": scan_id},
            },
        },
    ]
    # clean up
    delete_scan_results(models, scan_id)
