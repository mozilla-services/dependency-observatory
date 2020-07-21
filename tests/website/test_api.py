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

    response = client.get(f"/api/v1/jobs/{scan_id}/logs",)
    assert response.status == "404 NOT FOUND"

    # insert a fake result for the scan
    scan = models.db.session.query(models.Scan).filter_by(id=scan_id).first()
    result = models.JSONResult(data=[{"foo": "bar"}],)
    models.db.session.add(result)
    models.db.session.commit()
    scan.result_id = result.id
    models.db.session.add(scan)
    models.db.session.commit()

    response = client.get(f"/api/v1/jobs/{scan_id}/logs",)
    assert response.status == "200 OK"
    assert set(response.json.keys()) == {"data", "id", "url"}
    assert response.json["data"] == [{"foo": "bar"}]
    assert response.json["url"] is None
    assert isinstance(response.json["id"], int)
