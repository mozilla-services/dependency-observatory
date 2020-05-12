#!/bin/bash

(jq --version > /dev/null) || (apt-get update && apt-get install -y curl jq)

set -e

api_url=$1
if [[ "$api_url" = "" ]]; then
    api_url="http://localhost:8000"
fi

# check dockerflow
echo "testing ${api_url}/__heartbeat__"
diff -w tests/fixtures/__heartbeat__200.json <(curl -sS "${api_url}/__heartbeat__" | jq "")
echo "/__heartbeat__ matched expected output? (should be 0)" "$?"

echo "testing ${api_url}/__lbheartbeat__"
diff -w tests/fixtures/__lbheartbeat__200.json <(curl -sS "${api_url}/__lbheartbeat__" | jq "")
echo "/__lbheartbeat__ matched expected output? (should be 0)" "$?"

echo "testing ${api_url}/__version__"
diff -w tests/fixtures/__version__keys.json <(curl -sS "${api_url}/__version__" | jq 'keys')
echo "/__version__ returns expected keys? (should be 0)" "$?"


# test scanning
echo "testing ${api_url}/package?package_name=minimist&package_version=1.2.0 runs and scores a scan"
echo "sleeping for one second"
while :
do
    sleep 1
    response=$(curl -sSw '\n' "${api_url}/package?package_name=minimist&package_version=1.2.0" | jq '')
    task_status=$(echo -n "$response" | jq -rc '.task_status')
    status=$(echo -n "$response" | jq -rc '.status')
    echo ".task_status: ${task_status} .status: ${status}"
    if [[ "$status" = 'error' ]]; then
        echo "scan task errored"
        exit 1
    fi
    if [[ "$task_status" = 'FAILURE' ]]; then
        echo "queuing task failed"
        exit 1
    fi

    if [[ "$status" = 'scanned' ]]; then
       break
    fi
done
echo "scan succeeded with response:"
echo "$response"
