import pytest


@pytest.mark.unit
def test_invalid_create_job_params(client):
    response = client.post("/api/v1/jobs",)
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"_schema": ["Invalid input type."]}

    # missing name
    response = client.post("/api/v1/jobs", json={},)
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"name": ["Missing data for required field."]}

    # invalid name
    response = client.post("/api/v1/jobs", json={"name": "foo"},)
    assert response.status == "400 BAD REQUEST"
    assert response.json == {"description": "job not allowed or does not exist for app"}

    response = client.post(
        "/api/v1/jobs", json={"name": "foo", "args": [], "kwargs": {}, "extra": -1},
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == {"extra": ["Unknown field."]}


def delete_scan_results(models, scan_id: int):
    # delete any stray results
    [models.db.session.delete(scan) for scan in models.get_scan_results_by_id(scan_id)]
    models.db.session.commit()


def test_valid_create_job_and_get(models, client):
    scan_response = client.post(
        "/api/v1/jobs",
        json={"name": "scan_score_npm_package", "args": [], "kwargs": {}},
    )
    assert scan_response.status == "202 ACCEPTED"
    assert "id" in scan_response.json
    scan_id = scan_response.json["id"]

    response = client.get(f"/api/v1/jobs/{scan_id}",)
    assert response.status == "200 OK"

    delete_scan_results(models, scan_id)
    response = client.get(f"/api/v1/jobs/{scan_id}/logs",)
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

    response = client.get(f"/api/v1/jobs/{scan_id}/logs",)
    assert response.status == "200 OK"
    assert response.json == [
        {
            "id": results[1].id,
            "data": {
                "data": [{"spam": "cheese"}, {"line": 2}],
                "attributes": {"SCAN_ID": scan_id},
            },
        },
        {
            "id": results[0].id,
            "data": {"data": [{"foo": 0.5}], "attributes": {"SCAN_ID": scan_id}},
        },
    ]
    # clean up
    delete_scan_results(models, scan_id)
