import pytest


@pytest.mark.unit
def test_lbheartbeat(client):
    response = client.get("/__lbheartbeat__")
    assert response.status == "200 OK"


# hits the database so it isn't a unit test
def test_heartbeat(client):
    response = client.get("/__heartbeat__")
    assert response.status == "200 OK"


@pytest.mark.unit
def test_version_json(client):
    response = client.get("/__version__")
    assert response.status == "200 OK"
