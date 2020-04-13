import pytest

from depobs.website.do import create_app


@pytest.fixture
def app():
    app = create_app({"TESTING": True,})

    with app.app_context():
        pass

    yield app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
