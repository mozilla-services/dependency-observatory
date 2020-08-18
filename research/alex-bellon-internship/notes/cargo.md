# cargo

## General
- [**Semver**](https://semver.org/): Semantic version parsing and comparison. Semantic versioning is a set of rules for assigning version numbers.

## [Dependency Resolver](https://docs.rs/cargo/0.44.1/cargo/core/resolver/index.html)

- Solving a constraint graph is NP-hard
- Constraints
  - Each crate can have multiple dependencies (and ranges for dependencies)
  - Dependencies can appear more than once
- Algorithm
  - DFS, activating the newest version of a crate first, then going to the next option
  - Never activate an incompatible crate version
  - Always try to activate the newest version

## [`cargo install`](https://doc.rust-lang.org/cargo/commands/cargo-install.html)
- If the package is already installed, cargo will reinstall a package if any of these have changed
  - The package version and source
  - The set of binary names installed
  - The chosen features
  - The release mode (--debug)
  - The target (--target)

## [Specifying Dependencies](https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html)

- Caret requirements
  - Update is allowed if it does not change the leftmost nonzero number in the semver format
  ```
  ^1.2.3  :=  >=1.2.3, <2.0.0
  ^1.2    :=  >=1.2.0, <2.0.0
  ^1      :=  >=1.0.0, <2.0.0
  ^0.2.3  :=  >=0.2.3, <0.3.0
  ^0.2    :=  >=0.2.0, <0.3.0
  ^0.0.3  :=  >=0.0.3, <0.0.4
  ^0.0    :=  >=0.0.0, <0.1.0
  ^0      :=  >=0.0.0, <1.0.0
  ```
  - While SemVer says there is no compatibility before 1.0.0, Cargo considers `0.x.y` to be compatible with `0.x.z`, where `y ≥ z` and `x > 0`.
- Tilde requirements
  - If you specify a major, minor, and patch version or only a major and minor version, only patch-level changes are allowed. If you only specify a major version, then minor- and patch-level changes are allowed.
  ```
  ~1.2.3  := >=1.2.3, <1.3.0
  ~1.2    := >=1.2.0, <1.3.0
  ~1      := >=1.0.0, <2.0.0
  ```
- Wildcard requirements
  - Works how you would expect, any number is allowed to replace the asterisk
- Comparison requirements
  - You can specify one (or more) comparison requirements how you would expect (e.g. `> 1.0`, `= 3.0`, `<=2.3`, etc)
- You can also specify dependencies from other registries, from `git` repos, from paths
- You can specify multiple locations so that a `path` or `git` source is used locally, and then uses a registry version when it is published
  ```
  [dependencies]
  # Uses `my-bitflags` when used locally, and uses
  # version 1.0 from crates.io when published.
  bitflags = { path = "my-bitflags", version = "1.0" }

  # Uses the given git repo when used locally, and uses
  # version 1.0 from crates.io when published.
  smallvec = { git = "https://github.com/servo/rust-smallvec", version = "1.0" }
  ```
- Dependencies can also be specified for specific operating systems

## [Unstable Features](https://doc.rust-lang.org/nightly/cargo/reference/unstable.html#unstable-features)

#### minimal-versions
When a `Cargo.lock` file is generated, the `-Z minimal-versions` flag will resolve the dependencies to the minimum semver version that will satisfy the requirements (instead of the greatest version).

The intended use-case of this flag is to check, during continuous integration, that the versions specified in Cargo.toml are a correct reflection of the minimum versions that you are actually using. That is, if Cargo.toml says `foo = "1.0.0"` that you don't accidentally depend on features added only in `foo 1.5.0`.

## [Version selection in Cargo](https://aturon.github.io/tech/2018/07/25/cargo-version-selection/)

- Cargo chooses the newest possible version
- Reproducibility
  - If we choose the maximum version, there needs to be some record of the state of the versions to ensure reproducibility (like in a lockfile)
  - If we choose the minimum version, we do not need to deal with this
- Compatibility
  - If we choose the maximum version, then there will be an ecosystem-wide agreement about what versions of packages are compatible
  - If we choose the minimum version, then there is no agreement, as different dependencies can be satisfied with different minimum versions
- Maintainability
  - If we choose the maximum version, then development/maintenance/support is solely directed towards the newest version
  - If we choose the minimum version, there is a greater chance of users being vulnerable to old bugs
- For an existing lockfile, the version will not be updated with new releases. When the dependencies are adjusted, the lockfile will be updated to choose the newest version.
- Proposals for setting toolchain requirements/support
    - **Shared policy**: Set a clear ecosystem-wide expectation for level of compatibility. It is not a breaking change to update the compiler version required.
    - **Stated toolchain**: Specify toolchain requirements, and have them affect dependency resolution.
  - Control
    - Shared policy has limited control since there are not explicit toolchain versions the library must work with, but rather different release channels (LTS, stable, nightly)
    - For stated toolchain, everyone has a lot of control since authors can set which versions they support, and users can pick which version works for them
  - Compatibility
    - Shared policy only needs to worry about compatibility with LTS
    - Stated toolchain will get you the latest compatible version, but it may not be the newest version as that might require a new toolchain
  - Maintainability
    - Authors have to support an older version of the toolchain, but because users are more likely to use the newest version of a library, the bug reports will be relevant to the latest version
    - Authors will have to deal with bug reports for older versions since users are less likely to be compatible with the latest version of the library
- Checking minimal resolution
  - To get a precise lower bound, you need to resolve to the minimal version and check those versions against the ones listed in `Cargo.toml`
  - This is not super relevant right now since the default resolution is the newest version, but if the stated toolchain approach were to be implemented it would be needed
