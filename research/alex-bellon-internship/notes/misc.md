## APIs
- [crates.io API](https://github.com/hcpl/crates.io-http-api-reference)
- [PyPI API](https://warehouse.readthedocs.io/api-reference/)
- [libraries.io API](https://libraries.io/api)
    - Probably use this instead of PyPI's native API bc there's not much info

## Author vs. Contributor vs. Maintainer vs. Owner
- [Cargo](https://doc.rust-lang.org/cargo/reference/publishing.html#cargo-owner)
  - **Author**: Usually an individual, no practical purpose, up to interpretation. Set in crate metadata
  - **Owners**: Individuals or teams, set in the UI or by cargo.
    - Individuals can publish and add new owners,
    - Teams can publish but can not add new owners
- [NPM](https://github.com/npm/www/issues/133#issuecomment-284906561)
  - **Author**: Usually an individual, no practical purpose, up to interpretation. Set in metadata.
  - **Contributors**: User-supplied field in package.json, no practical purpose, up to interpretation
  - **Maintainers**: npm controlled list of usernames with permission to write to that package
    - Maintainers for a version is snapshot of maintainers at the time it was published
  - **npmUser**: Per-version metadata is the username of the authenticated account who wrote that version to the registry, must be a maintainer
  - **Owner**: Synonymous with "maintainer" or in the case of packages that are maintained by an org/@scoped packages belonging to a username, it's the scope (username or organization) that manages the access control for that package
- [PyPI](https://github.com/pypa/warehouse/issues/3157)
  - **Owner**: Owns a project, may add other collaborators for that project, and upload releases for a project. May delete files or releases. Can delete the entire project.
  - **Maintainer**: May upload releases for a project. Cannot add collaborators, delete files, delete releases or delete the project.
  - Author: Usually an individual, no practical purpose, up to interpretation. Set in metadata.

## Ideas
- [ ] Maintainer with highest # leaks
- [ ] Maintainer with largest reach
- [ ] Package with most leaks/person
- [ ] Compare whatever "scoring" we implement to the npms.io scores
- [ ] Number of dependents for the top package vs package #50, #100, etc

- Leaks
  - Leak in past year => "viable"
  - Keep track of percentages of viable leaks
  - Leaks since last publish
- Vulnerabilities
  - Keep track of vulns/advisories since last publish

## Etc

### Dependency Version Resolution
- Cargo: Highest Version
- NPM: Highest Version
- PyPI:
- Go: Minimal Version
