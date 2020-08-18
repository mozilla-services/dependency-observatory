# Finding Vulnerable Packages in Mozilla's Services

## Code Flow

1. Go through all of the [Mozilla services](https://gist.github.com/g-k/26f532ab03dddcb0df4dece094e2317e) and create a dictionary that maps packages to Mozilla services that depend on that package.
  - Output for [NPM](npm-packages.json) and [PyPI](pypi-packages.json)
  - I focused on NPM because it uses the most amount of packages, and NPM provides more metadata to work with than PyPI
2. Go through the results for the [most depended-on packages](../output/top-500/top-500-npm-results.json) and find the packages that are unmaintained (i.e. haven't had a release in the past year)
3. Find the intersection of the unmaintained packages and the packages that Mozilla uses (the `targets` list)
4. Go through each of the packages in `target` and see if they have any security advisories in [GitHub's Advisory Database](https://github.com/advisories)
5. Collect all of the advisories that were issued after the last release of the associated package and have not been withdrawn
6. Output the Mozilla services associated with the unmaintained packages with active vulnerabilities
