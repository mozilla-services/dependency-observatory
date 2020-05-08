#!/usr/bin/env bash

# prints newline delimited list of directories relative to
# CWD containing package.json files to stdout
#
# excludes node_modules/ directories
#
# example usage in fxa repo:
#
# $ find_package_json_files.sh
# .
# packages/123done
# packages/fxa-email-event-proxy
# ...


# check for and install missing required deps assuming a node debian base image
(rg --version > /dev/null) || (apt-get update && apt-get install -y ripgrep)

# case insensitive search for package.json filenames excluding files
# in node_modules/ directories
package_json_paths=$(rg --no-ignore --files --iglob "!node_modules/" --iglob 'package.json')
for package_json_path in $package_json_paths; do
    echo $(dirname "$package_json_path")
done
