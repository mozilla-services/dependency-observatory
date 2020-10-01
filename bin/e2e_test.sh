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
    fixture_dir="./tests/fixtures"
fi


# check dockerflow
echo "testing ${api_url}/__heartbeat__"
diff -w "${fixture_dir}/__heartbeat__200.json" <(curl -sS "${api_url}/__heartbeat__" | jq "")
echo "/__heartbeat__ matched expected output? (should be 0)" "$?"

echo "testing ${api_url}/__lbheartbeat__"
diff -w "${fixture_dir}/__lbheartbeat__200.json" <(curl -sS "${api_url}/__lbheartbeat__" | jq "")
echo "/__lbheartbeat__ matched expected output? (should be 0)" "$?"

echo "testing ${api_url}/__version__"
diff -w "${fixture_dir}/__version__keys.json" <(curl -sS "${api_url}/__version__" | jq 'keys')
echo "/__version__ returns expected keys? (should be 0)" "$?"


# test scanning a package
scan_id=$(curl  -sSw '\n' -X POST -H 'Content-Type: application/json' -H 'Connection: keep-alive' --compressed --data-raw '{"package_manager": "npm", "package_name": "ip-reputation-js-client", "package_versions_type": "latest", "scan_type": "scan_score_npm_package"}' "${api_url}/api/v1/scans" | jq '.id')
echo "started npm package scan with id ${scan_id}"


echo "sleeping for one second between progress checks"
while :
do
    sleep 1
    status=$(curl -sSw '\n' "${api_url}/api/v1/scans/${scan_id}" | jq -r '.status')
    echo "scan_status: ${status}"
    if [[ "$status" = 'failed' ]]; then
        echo "scan task errored with response:"
        echo "$response"
        exit 1
    fi

    if [[ "$status" = 'succeeded' ]]; then
       break
    fi
done
response=$(curl -sSw '\n' "${api_url}/package_report?package_manager=npm&package_name=ip-reputation-js-client&package_version=latest")
echo "package scan succeeded. Report response:"
echo "$response"


# test scanning dep files
scan_id=$(curl  -sSw '\n' -X POST -H 'Content-Type: application/json' -H 'Connection: keep-alive' --compressed --data-raw '{"package_manager": "npm", "scan_type": "scan_score_npm_dep_files", "manifest_url": "https://raw.githubusercontent.com/mozilla-services/ip-reputation-js-client/master/package.json"}' "${api_url}/api/v1/scans" | jq '.id')

echo "started npm dep files scan with id ${scan_id}"

echo "sleeping for one second between progress checks"
while :
do
    sleep 1
    status=$(curl -sSw '\n' "${api_url}/api/v1/scans/${scan_id}" | jq -r '.status')
    echo "scan_status: ${status}"
    if [[ "$status" = 'failed' ]]; then
        echo "scan task errored with response:"
        echo "$response"
        exit 1
    fi

    if [[ "$status" = 'succeeded' ]]; then
       break
    fi
done
response=$(curl -sSw '\n' "${api_url}/dep_files_reports/${scan_id}")
echo "dep file scan succeeded. Report response:"
echo "$response"
