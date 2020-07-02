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
