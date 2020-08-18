# pip

## [Satisfying Requirements](https://pip.pypa.io/en/stable/reference/pip_install/#satisfying-requirements)

- Once pip has a set of requirements to satisfy, it chooses the newest version that satisfies the given constraints
- pip installs dependencies before their dependents because
  - Concurrent use of the environment during the install is more likely to work
  - A failed install is less likely to leave a broken environment
- In the case of cyclic dependency, the first member of the cycle is installed last

## [Requirements Files](https://pip.pypa.io/en/stable/user_guide/)

- As of now **pip doesn't have true dependency resolution, it just uses the first specification it finds**
  - [GitHub issue](https://github.com/pypa/pip/issues/988)

## New Resolver

- [GitHub Project](https://github.com/pypa/pip/projects/5)
- [First issue asking for a resolver](https://github.com/pypa/pip/issues/988)

## Package Signatures

- The PyPI API has a field for each release that states whether the package has been signed (has_sig)
- [Python tools do not validate signatures in any way](https://github.com/pypa/twine/issues/157)
