import pytest


def test_lbheartbeat(client):
    response = client.get("/__lbheartbeat__")
    assert response.status == "200 OK"


def test_heartbeat(client):
    response = client.get("/__lbheartbeat__")
    assert response.status == "200 OK"


def test_version_json(client):
    response = client.get("/__version__")
    assert response.status == "200 OK"
