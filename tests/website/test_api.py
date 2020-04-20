import pytest
import json


def test_get_index(client):
    response = client.get("/")
    assert response.status == "200 OK"
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"
    assert b"Welcome to Mozilla's Dependency Observatory" in response.data


def test_get_package(client):
    response = client.get(
        "/package?package_name=@hapi/bounce&package_version=2.0.0&package_manager=npm"
    )
    # TODO: make this deterministic by preloading the fixture in DB so it always
    # returns 200 OK and never triggers a scan
    assert response.status == "200 OK" or response.status == "202 Accepted"

    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert response.headers["Content-Type"] == "application/json"

    payload = json.loads(response.data)
    assert payload["package"] == "@hapi/bounce"
    assert payload["version"] == "2.0.0"


def test_get_parents(client):
    response = client.get(
        "/parents?package_name=@hapi/bounce&package_version=2.0.0&package_manager=npm"
    )
    assert response.status == "200 OK"
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert response.headers["Content-Type"] == "application/json"

    payload = json.loads(response.data)
    assert payload["package"] == "@hapi/bounce"
    assert payload["version"] == "2.0.0"
    assert len(payload["parents"]) == 0


def test_get_vulnerabilities(client):
    response = client.get(
        "/vulnerabilities?package_name=@hapi/bounce&package_version=2.0.0&package_manager=npm"
    )
    assert response.status == "200 OK"
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert response.headers["Content-Type"] == "application/json"

    payload = json.loads(response.data)
    assert payload["package"] == "@hapi/bounce"
    assert payload["version"] == "2.0.0"
    assert len(payload["vulnerabilities"]) == 0


def test_get_statistics(client):
    response = client.get("/statistics")
    assert response.status == "200 OK"
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert response.headers["Content-Type"] == "application/json"

    payload = json.loads(response.data)
    print(payload)
    assert payload["package_versions"] >= 0
    assert payload["advisories"] >= 0
    assert payload["reports"] >= 0
