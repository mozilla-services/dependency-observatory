#!/bin/bash

# write a version.json to stdout per https://github.com/mozilla-services/Dockerflow/blob/master/docs/version_object.md

CI=${CI:-""}

if [[ "$CI" = "" ]]; then
    printf '{"commit":"%s","version":"%s","source":"https://github.com/mozilla-services/dependency-observatory","build":""}\n' \
            "$(git rev-parse HEAD)" \
            "$(git describe HEAD)"
else
    set -v
    printf '{"commit":"%s","version":"%s","source":"https://github.com/%s/%s","build":"%s"}\n' \
                "$CIRCLE_SHA1" \
                "$CIRCLE_TAG" \
                "$CIRCLE_PROJECT_USERNAME" \
                "$CIRCLE_PROJECT_REPONAME" \
                "$CIRCLE_BUILD_URL"
fi
