import datetime, json, math, pprint, requests

GITHUB_TOKEN = open("../../../github.token").read().strip("\n")


def main():
    # numPackages = [50, 100, 250, 500]
    numPackages = [500]
    for num in numPackages:
        unmaintained = True
        active = False
        analyze(num, unmaintained, active)


def analyze(numPackages, unmaintained=True, active=True):
    mozillaProjects = json.loads(open("npm-packages.json", "r").read())
    mozillaPackages = list(mozillaProjects.keys())

    targets = getTargets(numPackages, mozillaPackages, unmaintained)
    print(targets.keys())

    allNpmAdvisories = getAllNpmAdvisories()
    allNpmAdvisoriesPackages = dict()

    for i in range(len(allNpmAdvisories)):
        name = allNpmAdvisories[i]["module_name"]
        if name not in allNpmAdvisoriesPackages:
            allNpmAdvisoriesPackages[name] = []
        indices = allNpmAdvisoriesPackages[name]
        indices.append(i)
        allNpmAdvisoriesPackages[name] = indices

    possibleGithubVulns = list()
    possibleNpmVulns = list()

    for target in targets.keys():
        release = targets[target]

        githubAdvisories = getGithubAdvisories(target)
        newGithubAdvisories = getNewGithubAdvisories(githubAdvisories, release)
        if active:
            possibleGithubVulns += newGithubAdvisories
        else:
            possibleGithubVulns += githubAdvisories

        if target in allNpmAdvisoriesPackages.keys():
            npmAdvisories = getNpmAdvisories(
                allNpmAdvisories, allNpmAdvisoriesPackages[target]
            )
            newNpmAdvisories = getNewNpmAdvisories(npmAdvisories, release)
            if active:
                possibleNpmVulns += newNpmAdvisories
            else:
                possibleNpmVulns += npmAdvisories

    # TODO Fix assumptions that packages only have one vuln
    possibleVulns = dict()
    for vuln in possibleNpmVulns:
        package = vuln["module_name"]
        print(package)
        if package not in possibleVulns:
            possibleVulns[package] = {}
        serverities = possibleVulns[package]
        serverities["npm"] = vuln["metadata"]["exploitability"]
        possibleVulns[package] = serverities

    for vuln in possibleGithubVulns:
        package = vuln["package"]
        if package not in possibleVulns:
            possibleVulns[package] = {}
        serverities = possibleVulns[package]
        serverities["github"] = vuln["severity"]
        possibleVulns[package] = serverities

    for package in possibleVulns.keys():
        print("\n" + package)
        print(mozillaProjects[package])

    print(possibleVulns)

    output = open("top-" + str(numPackages) + "-vulnerabilities.json", "w")
    output.write(
        json.dumps(
            {"github": possibleGithubVulns, "npm": possibleNpmVulns},
            sort_keys=True,
            indent=2,
        )
    )


def getTargets(numPackages, npmPackages, unmaintained):
    npm = json.loads(
        open(
            "../output/top-"
            + str(numPackages)
            + "/top-"
            + str(numPackages)
            + "-npm-results.json"
        ).read()
    )

    if unmaintained:
        npmUnmaintained = {
            package["package"]: datetime.datetime.strptime(
                package["last-release"], "%Y-%m-%d %H:%M:%S"
            )
            for package in npm
            if package["maintained"] == False
        }

        targets = dict()
        for package in npmPackages:
            if package in npmUnmaintained.keys():
                targets[package] = npmUnmaintained[package]

        numTargets = len(targets)
        numUnmaintained = len(npmUnmaintained)
        print(
            "Mozilla uses "
            + str(numTargets)
            + "/"
            + str(numUnmaintained)
            + " ("
            + "{:.2%}".format(numTargets / numUnmaintained)
            + ") unmaintained packages in the top "
            + str(numPackages)
            + " most depended-on NPM packages"
        )

    else:
        npmUnmaintainedAndMaintained = {
            package["package"]: datetime.datetime.strptime(
                package["last-release"], "%Y-%m-%d %H:%M:%S"
            )
            for package in npm
        }

        targets = dict()
        for package in npmPackages:
            if package in npmUnmaintainedAndMaintained.keys():
                targets[package] = npmUnmaintainedAndMaintained[package]

        numTargets = len(targets)
        print(
            "Mozilla uses "
            + str(numTargets)
            + "/"
            + str(numPackages)
            + " ("
            + "{:.2%}".format(numTargets / numPackages)
            + ") of the packages in the top "
            + str(numPackages)
            + " most depended-on NPM packages"
        )

    return targets


def getGithubAdvisories(package):
    headers = {"Authorization": "token " + GITHUB_TOKEN}
    url = "https://api.github.com/graphql"

    query = (
        """
    {
        securityVulnerabilities(ecosystem: NPM, first: 100, package: \""""
        + package
        + """\", orderBy: {field: UPDATED_AT, direction: DESC}) {
            nodes {
                advisory {
                    id, description, permalink, publishedAt, severity, summary, updatedAt, withdrawnAt
                }
                package {
                    name
                }
            }
            pageInfo {
                endCursor, hasNextPage, hasPreviousPage, startCursor
            }
            totalCount
        }
    }
    """
    )

    response = json.loads(
        requests.post(url, json={"query": query}, headers=headers).content
    )
    nodes = response["data"]["securityVulnerabilities"]["nodes"]

    advisories = list()
    ids = list()
    for node in nodes:
        if (
            node["advisory"]["id"] not in ids
            and node["advisory"]["withdrawnAt"] == None
        ):
            advisory = node["advisory"]
            advisory["package"] = package
            advisories.append(advisory)
            ids.append(node["advisory"]["id"])

    return advisories


def getNewGithubAdvisories(advisories, release):
    newAdvisories = list()
    for advisory in advisories:
        published = datetime.datetime.strptime(
            advisory["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
        )
        if published > release:
            newAdvisories.append(advisory)

    return newAdvisories


def getAllNpmAdvisories():
    perPage = 100
    url = "https://registry.npmjs.org/-/npm/v1/security/advisories"

    numAdvisories = int(json.loads(requests.get(url).content)["total"])
    url += "?perPage=" + str(perPage) + "&page="

    pages = math.ceil(numAdvisories / perPage)
    advisories = list()

    for i in range(pages):
        try:
            response = json.loads(requests.get(url + str(i)).content)
        except Exception as e:
            print("Error getting advisories: " + str(e))
            exit()
        # TODO: add error handling for different response codes

        advisories += response["objects"]

    return advisories


def getNpmAdvisories(advisories, indices):
    result = [advisories[index] for index in indices]
    return result


def getNewNpmAdvisories(advisories, release):
    result = list()
    for advisory in advisories:
        published = datetime.datetime.strptime(
            advisory["created"], "%Y-%m-%dT%H:%M:%S.%fZ"
        ).replace(microsecond=0, tzinfo=None)
        if published > release:
            result.append(advisory)
    return result


main()
