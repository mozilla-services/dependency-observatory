from typing import Optional

import pytest

import depobs.worker.validators as validators


@pytest.mark.parametrize(
    "package_name, expected_validation_error",
    [
        ("request", None),
        ("@namespace/foo", None),
        (None, Exception("Invalid NPM package name. Must be a str.")),
        (
            "#!/usr/bin/env",
            Exception(
                r"Invalid NPM package name. Did not match regex: '[@a-zA-Z0-9][\\.-_@/a-zA-Z0-9]{0,213}'"
            ),
        ),
    ],
    ids=["name", "namespaced name", "none", "invalid name - shebang",],
)
@pytest.mark.unit
def test_get_npm_package_name_validation_error(
    package_name: str, expected_validation_error: Optional[Exception]
) -> None:
    if expected_validation_error is None:
        assert validators.get_npm_package_name_validation_error(package_name) is None
    else:
        err = validators.get_npm_package_name_validation_error(package_name)
        print(f"got {err} {expected_validation_error}")
        assert isinstance(err, Exception)
        assert str(err) == str(expected_validation_error)


@pytest.mark.parametrize(
    "package_version, expected_validation_error",
    [
        ("0.0.0", None),
        ("v0.0.0", None),
        ("1.2.3-alpha.1+exp.sha.5114f85", None),
        (None, Exception("Invalid NPM package version. Must be a str.")),
        (
            "#!/usr/bin/env",
            Exception(
                r"Invalid NPM package version. Did not match regex: '(=v)?           # strip leading = and v\n[0-9]+\\.[0-9]+\\.[0-9]+  # major minor and patch versions (TODO: check if positive ints)\n[-]?[-\\.0-9A-Za-z]*       # optional pre-release version e.g. -alpha.1 (TODO: split out identifiers)\n[+]?[-\\.0-9A-Za-z]*       # optional build metadata e.g. +exp.sha.5114f85\n'"
            ),
        ),
    ],
    ids=[
        "semver",
        "semver w/ leading v",
        "semver w/ prerelease version and bulid metadata",
        "none",
        "invalid name - shebang",
    ],
)
@pytest.mark.unit
def test_get_npm_package_version_validation_error(
    package_version: str, expected_validation_error: Optional[Exception]
) -> None:
    if expected_validation_error is None:
        assert (
            validators.get_npm_package_version_validation_error(package_version) is None
        )
    else:
        err = validators.get_npm_package_version_validation_error(package_version)
        print(f"got {err} {expected_validation_error}")
        assert isinstance(err, Exception)
        assert str(err) == str(expected_validation_error)
