import re
from typing import Optional


# The name must be less than or equal to 214 characters. This includes the scope for scoped packages.
# The name can’t start with a dot or an underscore.
# New packages must not have uppercase letters in the name.
# The name ends up being part of a URL, an argument on the command line, and a folder name. Therefore, the name can’t contain any non-URL-safe characters.
#
# https://docs.npmjs.com/files/package.json#name
NPM_PACKAGE_NAME_RE = re.compile(
    r"""[@a-zA-Z0-9][\.-_@/a-zA-Z0-9]{0,213}""",
    re.VERBOSE,
)


def get_npm_package_name_validation_error(package_name: str) -> Optional[Exception]:
    """returns an Exception if package name is invalid or None if it is valid"""
    if not isinstance(package_name, str):
        return Exception("Invalid NPM package name. Must be a str.")

    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        return Exception(
            f"Invalid NPM package name. Did not match regex: {NPM_PACKAGE_NAME_RE.pattern!r}"
        )

    return None


# Version must be parseable by node-semver, which is bundled with npm as a dependency.
#
# https://docs.npmjs.com/files/package.json#version
#
# https://docs.npmjs.com/misc/semver#versions
NPM_PACKAGE_VERSION_RE = re.compile(
    r"""^([=v])?           # strip leading = and v
[0-9]+\.[0-9]+\.[0-9]+  # major minor and patch versions (TODO: check if positive ints)
[-]?[-\.0-9A-Za-z]*       # optional pre-release version e.g. -alpha.1 (TODO: split out identifiers)
[+]?[-\.0-9A-Za-z]*       # optional build metadata e.g. +exp.sha.5114f85
$""",
    re.VERBOSE,
)


def get_npm_package_version_validation_error(package_name: str) -> Optional[Exception]:
    """returns an Exception if package version is invalid or None if it is valid"""
    if not isinstance(package_name, str):
        return Exception("Invalid NPM package version. Must be a str.")

    if not re.match(NPM_PACKAGE_NAME_RE, package_name):
        return Exception(
            f"Invalid NPM package version. Did not match regex: {NPM_PACKAGE_VERSION_RE.pattern!r}"
        )

    return None


# Version must be parseable by node-semver, which is bundled with npm as a dependency.
#
# https://docs.npmjs.com/files/package.json#version
#
# https://docs.npmjs.com/misc/semver#versions
NPM_PACKAGE_RELEASE_VERSION_RE = re.compile(
    r"""^([=v])?           # strip leading = and v
[0-9]+\.[0-9]+\.[0-9]+  # major minor and patch versions (TODO: check if positive ints)
([+][-\.0-9A-Za-z]*)?     # optional build metadata e.g. 3+exp.sha.5114f85
$""",
    re.VERBOSE,
)


def is_npm_release_package_version(package_version: str) -> bool:
    return bool(re.match(NPM_PACKAGE_RELEASE_VERSION_RE, package_version))
