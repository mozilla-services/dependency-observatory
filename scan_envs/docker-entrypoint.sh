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

JOB_NAME=${JOB_NAME:-"undefined-job"}
BUILD_TARGET=${BUILD_TARGET:-""}
INSTALL_TARGET=${INSTALL_TARGET:-""}
PACKAGE_NAME=${PACKAGE_NAME:-""}
PACKAGE_VERSION=${PACKAGE_VERSION:-""}
GCP_PUBSUB_TOPIC=${GCP_PUBSUB_TOPIC:-""}
GCP_PROJECT_ID=${GCP_PROJECT_ID:-""}

echo "starting job ${JOB_NAME}"

# let gcloud sdk use a writable config
CLOUDSDK_CONFIG=$(mktemp -d)
export CLOUDSDK_CONFIG
export CLOUDSDK_CORE_PROJECT="$GCP_PROJECT_ID"

# use provided service account creds when set for dev (on GCP gcloud
# elsewhere use the cluster config)
if [ ! -z "${GOOGLE_APPLICATION_CREDENTIALS+default}" ]; then
    test -f "$GOOGLE_APPLICATION_CREDENTIALS"
    export CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE="$GOOGLE_APPLICATION_CREDENTIALS"
fi

function publish_message () {
    # NB: max message size is 10MB https://cloud.google.com/pubsub/quotas#resource_limits
    # NB: max attribute key size is 256 bytes max key value 1024 bytes
    message=$1
    gcloud pubsub topics publish "$GCP_PUBSUB_TOPIC" --message "$message" --attribute JOB_NAME="$JOB_NAME"
}

message_temp=$(mktemp)

# validate input env vars (TODO: validate combinations)
case "$LANGUAGE" in
    nodejs)
        LANGUAGE_VERSION="$(node --version)"
        ;;
    rust)
        LANGUAGE_VERSION="$(rustc --version)"
        ;;
    *)
        jq -cnM --arg invalid_value "$LANGUAGE" '{type: "validation_error", message: "unknown language", $invalid_value}' | tee -a "$message_temp"
        publish_message "$(cat "$message_temp")"
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
        jq -cnM --arg invalid_value "$PACKAGE_MANAGER" '{type: "validation_error", message: "unknown package_manager", $invalid_value}' | tee -a "$message_temp"
        publish_message "$(cat "$message_temp")"
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
            TASK_COMMAND="jq -cnM --arg name \"$PACKAGE_NAME\" --arg version \"$PACKAGE_VERSION\" '{dependencies: {}} | .dependencies[\$name] = \$version' | tee -a package.json"
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
            jq -cnM --arg invalid_value "${LANGUAGE}-${PACKAGE_MANAGER}-${TASK_NAME}" "{type: \"not_implemented_error\", message: \"do not know how to ${TASK_NAME} for language and package manager\", \$invalid_value}" | tee -a "$message_temp"
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
       '{type: "task_result", $name, $command, $working_dir, $exit_code, $stdout, $stderr, $versions, $envvar_args}' | tee -a "$message_temp"
    shift
done
jq -cnM '{type: "task_complete"}' | tee -a "$message_temp"
ls -lh "$message_temp"
publish_message "$(jq -s '.' "$message_temp")"

# TODO: add find_git_refs task
#   git fetch --tags origin # all tags
#   then sort tags from newest to oldest tagging time https://git-scm.com/docs/git-for-each-ref/
#   git for-each-ref --sort=-taggerdate --format="%(refname:short)\t%(taggerdate:unix)\t%(creatordate:unix)" refs/tags
#   tag_name, tag_ts, commit_ts = [part.strip('",') for part in line.split("\t", 2)]

# TODO: add git clone
# TODO: look into partial clones and sparse checkouts
# https://github.com/git/git/blob/master/Documentation/technical/partial-clone.txt
# https://github.blog/2020-01-13-highlights-from-git-2-25/#sparse-checkouts
# git clone --depth=1 --origin origin {repo_url} repo

# TODO: ensure ref task
#   git fetch origin {commit} # commit per https://stackoverflow.com/a/30701724
#   or: git fetch origin -f tag {tag_name} --no-tags # tag
#   or: git fetch {remote} {branch}  # branch
#   then: git checkout {ref.value}
#
# get_commit: git rev-parse HEAD
# get_branch: git rev-parse --abbrev-ref HEAD
# get_tag: git tag -l --points-at HEAD
# get_committer_timestamp: git show -s --format="%ct" HEAD
#
# TODO: add find_dep_files task with params:
# rg --no-ignore --files --iglob {search_pattern}.. (prefix with ! to ignore)
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
