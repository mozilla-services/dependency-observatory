from typing import Optional

import pytest

import depobs.worker.validators as m


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
        assert m.get_npm_package_name_validation_error(package_name) is None
    else:
        err = m.get_npm_package_name_validation_error(package_name)
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
        assert m.get_npm_package_version_validation_error(package_version) is None
    else:
        err = m.get_npm_package_version_validation_error(package_version)
        print(f"got {err} {expected_validation_error}")
        assert isinstance(err, Exception)
        assert str(err) == str(expected_validation_error)


@pytest.mark.parametrize(
    "package_version,is_release_version",
    [
        ("0.0.0", True),
        ("v0.0.0", True),
        ("0.0.0+exp.sha.5114f85", True),
        ("v0.0.0-rc.1", False),
        ("v0.0.0-rc1", False),
        ("1.2.3-alpha.1+exp.sha.5114f85", False),
        ("#!/usr/bin/env", False,),
        ("1.0.0-rc.3", False),
        ("1.0.0-beta", False),
        ("1.0.0-beta2", False),
        ("2.0.0-beta", False),
        ("2.0.0-beta2", False),
        ("2.0.0-beta3", False),
        ("2.0.0-rc2", False),
        ("3.0.0-alpha5", False),
        ("3.0.0-beta7", False),
        ("5.0.0-alpha.1", False),
    ],
)
@pytest.mark.unit
def test_get_npm_package_version_validation_error(
    package_version: str, is_release_version: bool
) -> None:
    assert m.is_npm_release_package_version(package_version) == is_release_version
