#!/bin/bash
set -e

USAGE="
Run one or more repo tasks in a container and write their task
output to stdout as json lines.

Requires env vars:

LANGUAGE 'nodejs, or 'rust'
PACKAGE_MANAGER 'cargo', 'npm', or 'yarn'

Usage: $0 [repo_task]+
"
if [ $# -lt 1 ]; then
        echo "$USAGE"
        exit 1
fi

GIT_VERSION="$(git --version)"
RG_VERSION="$(rg --version)"
JQ_VERSION="$(jq --version)"

LANGUAGE=${LANGUAGE}
PACKAGE_MANAGER=${PACKAGE_MANAGER}

BUILD_TARGET=${BUILD_TARGET:-""}
INSTALL_TARGET=${INSTALL_TARGET:-""}
PACKAGE_NAME=${PACKAGE_NAME:-""}
PACKAGE_VERSION=${PACKAGE_VERSION:-""}

# validate input env vars (TODO: validate combinations)
case "$LANGUAGE" in
    nodejs)
        LANGUAGE_VERSION="$(node --version)"
        ;;
    rust)
        LANGUAGE_VERSION="$(rustc --version)"
        ;;
    *)
        jq -cnM --arg invalid_value "$LANGUAGE" '{type: "validation_error", message: "unknown language", $invalid_value}'
        exit 1
        ;;
esac

case "$PACKAGE_MANAGER" in
    cargo)
        PACKAGE_MANAGER_VERSION="$(cargo --version)"
        ;;
    npm)
        PACKAGE_MANAGER_VERSION="$(npm --version)"
        ;;
    yarn)
        PACKAGE_MANAGER_VERSION="$(yarn --version)"
        ;;
    *)
        jq -cnM --arg invalid_value "$PACKAGE_MANAGER" '{type: "validation_error", message: "unknown package_manager", $invalid_value}'
        exit 1
        ;;
esac

VERSIONS=$(jq -cnM \
       --arg "git" "$GIT_VERSION" \
       --arg "jq" "$JQ_VERSION" \
       --arg "rg" "$RG_VERSION" \
       --arg "$LANGUAGE" "$LANGUAGE_VERSION" \
       --arg "$PACKAGE_MANAGER" "$PACKAGE_MANAGER_VERSION" \
       "{\$git, \$jq, \$rg, \$$LANGUAGE, \$$PACKAGE_MANAGER}")

ENVVAR_ARGS=$(jq -cnM \
                 --arg "LANGUAGE" "$LANGUAGE" \
                 --arg "PACKAGE_MANAGER" "$PACKAGE_MANAGER" \
                 --arg "BUILD_TARGET" "$BUILD_TARGET" \
                 --arg "INSTALL_TARGET" "$INSTALL_TARGET" \
                 --arg "PACKAGE_NAME" "$PACKAGE_NAME" \
                 --arg "PACKAGE_VERSION" "$PACKAGE_VERSION" \
                 '{$LANGUAGE, $PACKAGE_MANAGER, $BUILD_TARGET, $INSTALL_TARGET, $PACKAGE_NAME, $PACKAGE_VERSION}')

# process input task names one at a time
while (( $# )); do
    TASK_NAME=$1
    case "${LANGUAGE}-${PACKAGE_MANAGER}-${TASK_NAME}" in
        rust-cargo-audit)
            # cargo audit --version
            # NB: requires Cargo.lock
            TASK_COMMAND="cargo audit --json"
            ;;
        rust-cargo-build)
            # NB: requires Cargo.toml
            # creates target/package/<package name>-<pkg version>.crate
            TASK_COMMAND="cargo build -p \"$BUILD_TARGET\""
            ;;
        rust-cargo-install)
            # NB: requires a Cargo.toml file and uses the Cargo.lock when present
            TASK_COMMAND="cargo install --all-features --locked \"$INSTALL_TARGET\""
            ;;
        rust-cargo-list_metadata)
            # NB: requires Cargo.toml
            TASK_COMMAND="cargo metadata --format-version 2 --locked"
            ;;

        nodejs-npm-audit)
            # NB: requires a package.json manifest and an npm lockfile (package-lock.json or npm-shrinkwrap.json)
            TASK_COMMAND="npm audit --json"
            ;;
        nodejs-npm-build)
            # NB: requires package.json and doesn't take a package name
            TASK_COMMAND="npm pack ."
            ;;
        nodejs-npm-ci)
            # NB: requires a package.json manifest and an npm lockfile (package-lock.json or npm-shrinkwrap.json)
            # NB: errors for missing package-lock.json or npm-shrinkwrap.json and does not update the files
            TASK_COMMAND="npm ci"
            ;;
        nodejs-npm-install)
            # NB: creates or update package-lock.json or npm-shrinkwrap.json
            # NB: requires a package.json
            TASK_COMMAND="npm install --save=true $INSTALL_TARGET"
            ;;
        nodejs-npm-list_metadata)
            # NB: requires a package.json file and "npm ci" or "npm install" to not just show a bunch of missing warnings/errors
            TASK_COMMAND="npm list --json"  # or "npm list --json --long"
            ;;
        nodejs-npm-write_manifest)
            # write a package.json file to so npm audit doesn't error out
            TASK_COMMAND="jq -cnM --arg name \"$PACKAGE_NAME\" --arg version \"$PACKAGE_VERSION\" '{dependencies: {}} | .dependencies[\$name] = \$version' | tee package.json"
            ;;

        nodejs-yarn-audit)
            # NB: requires a package.json manifest and a yarn.lock
            TASK_COMMAND="yarn audit --json --frozen-lockfile"
            ;;
        nodejs-yarn-build)
            # NB: requires package.json and doesn't take a package name
            TASK_COMMAND="yarn pack --non-interactive ."
            ;;
        nodejs-yarn-install)
            # NB: requires package.json and yarn.lock
            TASK_COMMAND="yarn install --frozen-lockfile \"$INSTALL_TARGET\""
            ;;
        nodejs-yarn-list_metadata)
            # NB: requires a package.json and yarn.lock
            TASK_COMMAND="yarn list --json --frozen-lockfile"
            ;;
        *)
            jq -cnM --arg invalid_value "${LANGUAGE}-${PACKAGE_MANAGER}-${TASK_NAME}" "{type: \"not_implemented_error\", message: \"do not know how to ${TASK_NAME} for language and package manager\", \$invalid_value}"
            shift
            continue
            ;;
    esac

    # https://mywiki.wooledge.org/BashFAQ/002

    stdout_temp=$(mktemp)
    set +e # don't stop if the command fails
    stderr=$(eval "$TASK_COMMAND" 2>&1 >"$stdout_temp")
    status=$?
    set -e
    stdout=$(cat "$stdout_temp")

    jq -cnM \
       --arg name "$TASK_NAME" \
       --arg command "$TASK_COMMAND" \
       --arg working_dir "$(pwd)" \
       --argjson exit_code "$status" \
       --arg stdout "$stdout" \
       --arg stderr "$stderr" \
       --argjson versions "$VERSIONS" \
       --argjson envvar_args "$ENVVAR_ARGS" \
       '{type: "task_result", $name, $command, $working_dir, $exit_code, $stdout, $stderr, $versions, $envvar_args}'
    shift
done

# TODO: add git clone / ensure ref task
# TODO: add find_git_refs task
# TODO: add find_dep_files task with params:
#
# cargo
# patterns
#   search_glob cargo.lock LOCKFILE
#   search_glob cargo.toml MANIFEST_FILE
#
# npm
# patterns  # ripgrep patterns to search for the dependency files
#   search_glob package.json MANIFEST_FILE
#   search_glob package-lock.json LOCKFILE
#   search_glob npm-shrinkwrap.json LOCKFILE
#
# ignore_patterns "node_modules/"
#
# yarn
# patterns
#   search_glob package.json MANIFEST_FILE
#   search_glob yarn.lock LOCKFILE
