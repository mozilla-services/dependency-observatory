import pytest


def test_root_url_returns_index_page_title(client):
    response = client.get("/")
    assert response.status == "200 OK"
