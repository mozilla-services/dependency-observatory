import pytest


invalid_scan_cases = {
    "empty": [dict(), {"_schema": ["Invalid input type."]}],
    "empty_json": [
        dict(json=dict()),
        {
            "package_manager": ["Missing data for required field."],
            "package_name": ["Missing data for required field."],
            "package_versions_type": ["Missing data for required field."],
            "scan_type": ["Missing data for required field."],
        },
    ],
    "invalid scan_type": [
        dict(
            json={
                "scan_type": "foo",
                "package_name": "test",
                "package_manager": "npm",
                "package_versions_type": "releases",
            }
        ),
        {"scan_type": ["Must be equal to scan_score_npm_package."]},
    ],
    "extra_field": [
        dict(
            json={
                "scan_type": "scan_score_npm_package",
                "package_name": "test",
                "package_manager": "npm",
                "package_versions_type": "releases",
                "extra": -1,
            }
        ),
        {"extra": ["Unknown field."]},
    ],
    "invalid_dep_files_scan_url": [
        dict(
            json={
                "scan_type": "scan_score_npm_dep_files",
                "package_manager": "npm",
                "manifest_url": "not-a-url",
            }
        ),
        {"manifest_url": ["Not a valid URL."]},
    ],
}


@pytest.mark.parametrize(
    "post_kwargs, response_json",
    invalid_scan_cases.values(),
    ids=invalid_scan_cases.keys(),
)
@pytest.mark.unit
def test_invalid_create_scan_params(client, post_kwargs, response_json):
    response = client.post("/api/v1/scans", **post_kwargs)
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json == response_json


def delete_scan_results(models, scan_id: int):
    # delete any stray results
    [models.db.session.delete(scan) for scan in models.get_scan_results_by_id(scan_id)]
    models.db.session.commit()


def test_valid_create_scan_package_job_and_get(
    models, client, valid_package_scan_payload
):
    scan_response = client.post(
        "/api/v1/scans",
        json=valid_package_scan_payload,
    )
    assert scan_response.status == "202 ACCEPTED"
    assert "id" in scan_response.json
    scan_id = scan_response.json["id"]

    response = client.get(
        f"/api/v1/scans/{scan_id}",
    )
    assert response.status == "200 OK"

    delete_scan_results(models, scan_id)
    response = client.get(
        f"/api/v1/scans/{scan_id}/logs",
    )
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

    response = client.get(
        f"/api/v1/scans/{scan_id}/logs",
    )
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


def test_valid_create_scan_package_job_and_get(
    models, client, valid_package_scan_payload
):
    scan_response = client.post(
        "/api/v1/scans",
        json=valid_package_scan_payload,
    )
    assert scan_response.status == "202 ACCEPTED"
    assert "id" in scan_response.json
    scan_id = scan_response.json["id"]

    response = client.get(
        f"/api/v1/scans/{scan_id}",
    )
    assert response.status == "200 OK"

    delete_scan_results(models, scan_id)
    response = client.get(
        f"/api/v1/scans/{scan_id}/logs",
    )
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

    response = client.get(
        f"/api/v1/scans/{scan_id}/logs",
    )
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
