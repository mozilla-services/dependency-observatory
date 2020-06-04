#!/bin/bash

(jq --version > /dev/null) || (apt-get update && apt-get install -y curl jq)

set -e

# NB: requires tests/fixtures/ e.g. as copied from unit test scripts
api_url=$1
if [[ "$api_url" = "" ]]; then
    api_url="http://localhost:8000"
fi

fixture_dir=$2
if [[ "$fixture_dir" = "" ]]; then
    fixture_dir="."
fi


# check dockerflow
echo "testing ${api_url}/__heartbeat__"
diff -w "${fixture_dir}/tests/fixtures/__heartbeat__200.json" <(curl -sS "${api_url}/__heartbeat__" | jq "")
echo "/__heartbeat__ matched expected output? (should be 0)" "$?"

echo "testing ${api_url}/__lbheartbeat__"
diff -w "${fixture_dir}/tests/fixtures/__lbheartbeat__200.json" <(curl -sS "${api_url}/__lbheartbeat__" | jq "")
echo "/__lbheartbeat__ matched expected output? (should be 0)" "$?"

echo "testing ${api_url}/__version__"
diff -w "${fixture_dir}/tests/fixtures/__version__keys.json" <(curl -sS "${api_url}/__version__" | jq 'keys')
echo "/__version__ returns expected keys? (should be 0)" "$?"


# test scanning
echo "testing ${api_url}/package?package_name=%40hapi%2Fbounce&package_version=2.0.0 runs and scores a scan"
echo "sleeping for one second"
while :
do
    sleep 1
    response=$(curl -sSw '\n' "${api_url}/package?package_name=%40hapi%2Fbounce&package_version=2.0.0" | jq '')
    task_status=$(echo -n "$response" | jq -rc '.task_status')
    status=$(echo -n "$response" | jq -rc '.status')
    echo ".task_status: ${task_status} .status: ${status}"
    if [[ "$status" = 'error' ]]; then
        echo "scan task errored with response:"
        echo "$response"
        exit 1
    fi
    if [[ "$task_status" = 'FAILURE' ]]; then
        echo "queuing task failed with response:"
        echo "$response"
        exit 1
    fi

    if [[ "$status" = 'scanned' ]]; then
       break
    fi
done
echo "scan succeeded with response:"
echo "$response"
