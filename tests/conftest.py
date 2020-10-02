import pytest

from depobs.website.do import create_app


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "API_TOKENS": {
                "test-api-key": "admin",
            },
        }
    )
    yield app


@pytest.fixture
def models(app):
    import depobs.database.models as models

    with app.app_context():
        yield models


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def valid_package_scan_payload():
    return {
        "scan_type": "scan_score_npm_package",
        "package_name": "@hapi/bounce",
        "package_manager": "npm",
        "package_versions_type": "releases",
    }


@pytest.fixture
def valid_dep_files_scan_payload():
    return {
        "scan_type": "scan_score_npm_dep_files",
        "package_manager": "npm",
        "manifest_url": "https://raw.githubusercontent.com/mozilla-services/ip-reputation-js-client/master/package.json",
        "lockfile_url": "https://raw.githubusercontent.com/mozilla-services/ip-reputation-js-client/master/package-lock.json",
        # "shrinkwrap_url":
    }
