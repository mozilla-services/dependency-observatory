import argparse, datetime, hashlib, json, math, pprint, requests, sys, time, urllib

HIBP_ANON_TOKEN = open("../../hibp.token").read().strip("\n")
HIBP_V3_TOKEN = open("../../hibp-v3.token").read().strip("\n")
GITHUB_TOKEN = open("../../github.token").read().strip("\n")
LIBRARIES_TOKEN = open("../../libraries.token").read().strip("\n")

NOW = datetime.datetime.utcnow()


def main():
    # Supported package managers: 'cargo', 'npm', 'pypi'
    packageManagers = list()

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_all = subparsers.add_parser("all")
    parser_all.add_argument("numPackages", type=int)

    parser_top = subparsers.add_parser("top")
    parser_top.add_argument("numPackages", type=int)
    parser_top.add_argument("packageManager", choices=["cargo", "npm", "pypi"])

    parser_list = subparsers.add_parser("list")
    parser_list.add_argument("packageManager", choices=["cargo", "npm", "pypi"])
    parser_list.add_argument("packageList", type=argparse.FileType("r"))

    args = parser.parse_args()

    if args.command == "top":
        packageManager = args.packageManager
        numPackages = args.numPackages
        runAnalysis(packageManager, numPackages)
    elif args.command == "all":
        packageManagers = ["cargo", "npm", "pypi"]
        numPackages = args.numPackages
        for packageManager in packageManagers:
            runAnalysis(packageManager, numPackages)
    elif args.command == "list":
        packageManager = args.packageManager
        packageList = args.packageList.read().splitlines()
        numPackages = len(packageList)
        runAnalysis(packageManager, numPackages, packageList)


def runAnalysis(packageManager, numPackages, packageList=None):
    outputContent = list()
    outputContentRaw = list()

    if packageList:
        packages = packageList  # TODO: make sure these are valid package names (?)
    else:
        packages = getPackages(packageManager, numPackages)

    for package in packages:
        packageInfo, fullResponse = getPackageInfo(package, packageManager)
        outputContent.append(packageInfo)
        outputContentRaw.append({package: fullResponse})

    exit()

    output = open(
        "output/" + packageManager + "-top-" + str(numPackages) + "-results.json", "w"
    )  # processed results
    output.write(json.dumps(outputContent))
    output.close()

    outputRaw = open(
        "output/" + packageManager + "-top-" + str(numPackages) + "-results-raw.json",
        "w",
    )  # full, raw responses
    outputRaw.write(json.dumps(outputContentRaw))
    outputRaw.close()


def getPackages(packageManager, numPackages):
    output = open(
        "lists/" + packageManager + "-top-" + str(numPackages) + "-packages.txt", "w"
    )

    packages = list()
    perPage = 100
    pages = math.ceil(numPackages / perPage)

    for i in range(1, pages + 1):

        response = None
        while not response or response.status_code != 200:
            time.sleep(2)
            response = requests.get(
                "https://libraries.io/api/search?q=&platforms="
                + urllib.parse.quote_plus(packageManager)
                + "&sort=dependents_count&per_page="
                + str(perPage)
                + "&page="
                + str(i)
                + "&api_key="
                + LIBRARIES_TOKEN
            )

        # TODO: add error handling for different response codes

        mostDepended = json.loads(response.content)
        for package in mostDepended:
            if len(packages) < numPackages:
                packages.append(package["name"])
            else:
                break

    output.write(
        str(packages)
        .replace("[", "")
        .replace("]", "")
        .replace("'", "")
        .replace(", ", "\n")
    )
    output.close()

    return packages


def getPackageInfo(package, packageManager):
    if packageManager == "cargo":
        return getCargoInfo(package)
    elif packageManager == "npm":
        return getNpmInfo(package)
    elif packageManager == "pypi":
        return getPypiInfo(package)
    else:
        return None


def getCargoInfo(package):
    response = json.loads(
        requests.get(
            "https://crates.io/api/v1/crates/" + urllib.parse.quote_plus(package)
        ).content
    )
    metadata = response["crate"]
    raw = [response]

    result = dict()

    emails, response = getCargoEmails(package)
    raw.append(response)

    response = json.loads(
        requests.get(
            "https://crates.io/api/v1/crates/"
            + urllib.parse.quote_plus(package)
            + "/reverse_dependencies"
        ).content
    )
    dependents = response["meta"]["total"]
    raw.append(response)

    leaks, totalLeaks, totalViableLeaks, avgLeaks, avgViableLeaks = getLeaks(emails)
    release, maintained = inPastYear(metadata["updated_at"], "%Y-%m-%dT%H:%M:%S.%f%z")

    dependencies = getCargoDependencies(package, [], True)
    (
        transitiveDependencies,
        transitiveUniqueEmails,
        transitiveLeaks,
        transitiveTotalLeaks,
        transitiveTotalViableLeaks,
    ) = calculateAttackSurface(package, "cargo")
    source = metadata["repository"]
    repo = source.replace("https://github.com/", "")
    ci = checkCI(repo)

    result["package"] = package
    result["emails"] = emails
    result["source"] = source
    result["last-release"] = str(release)
    result["downloads"] = metadata["downloads"]
    result["dependents"] = dependents
    result["leaks"] = leaks
    result["total-leaks"] = totalLeaks
    result["total-viable-leaks"] = totalViableLeaks
    result["average-leaks"] = avgLeaks
    result["average-viable-leaks"] = avgViableLeaks
    result["maintained"] = maintained
    result["dependencies"] = dependencies
    result["transitive-dependencies"] = transitiveDependencies
    result["transitive-emails"] = transitiveUniqueEmails
    result["transitive-leaks"] = transitiveLeaks
    result["transitive-total-leaks"] = transitiveTotalLeaks
    result["transitive-total-viable-leaks"] = transitiveTotalViableLeaks

    printResult(result, "cargo")
    return result, raw


def getCargoEmails(package):
    # This includes both individual maintainers and teams, but right now we only look at individuals
    response = requests.get(
        "https://crates.io/api/v1/crates/"
        + urllib.parse.quote_plus(package)
        + "/owners"
    ).content

    response = json.loads(response)
    githubAccts = [
        user["url"].replace("https://github.com/", "")
        for user in response["users"]
        if user["kind"] == "user"
    ]
    raw = response

    emails = list()
    headers = {"Authorization": "token " + GITHUB_TOKEN}
    for account in githubAccts:
        response = json.loads(
            requests.get(
                "https://api.github.com/users/" + urllib.parse.quote_plus(account),
                headers=headers,
            ).content
        )
        if "email" in response:
            emails.append(response["email"])
    emails = list(filter(None, emails))
    return emails, raw


def getNpmInfo(package):
    response = json.loads(
        requests.get(
            "https://api.npms.io/v2/package/" + urllib.parse.quote_plus(package)
        ).content
    )
    metadata = response["collected"]["metadata"]

    result = dict()
    emails = list()

    if "maintainers" in metadata:
        maintainers = metadata["maintainers"]
        for maintainer in maintainers:
            if "email" in maintainer:
                email = maintainer["email"]
                emails.append(email)
        result["emails"] = emails

    leaks, totalLeaks, totalViableLeaks, avgLeaks, avgViableLeaks = getLeaks(emails)
    release, maintained = inPastYear(metadata["date"], "%Y-%m-%dT%H:%M:%S.%fZ")
    dependencies = getNpmDependencies(package, [], True)
    (
        transitiveDependencies,
        transitiveUniqueEmails,
        transitiveLeaks,
        transitiveTotalLeaks,
        transitiveTotalViableLeaks,
    ) = calculateAttackSurface(package, "npm")
    source = (
        metadata["links"]["repository"] if "repository" in metadata["links"] else ""
    )
    repo = source.replace("https://github.com/", "")
    ci = checkCI(repo)

    result["package"] = package
    result["source"] = source
    result["ci"] = ci
    result["last-release"] = str(release)
    result["downloads"] = int(response["evaluation"]["popularity"]["downloadsCount"])
    result["dependents"] = response["collected"]["npm"]["dependentsCount"]
    result["leaks"] = leaks
    result["total-leaks"] = totalLeaks
    result["total-viable-leaks"] = totalViableLeaks
    result["average-leaks"] = avgLeaks
    result["average-viable-leaks"] = avgViableLeaks
    result["maintained"] = maintained
    result["dependencies"] = dependencies
    result["transitive-dependencies"] = transitiveDependencies
    result["transitive-emails"] = transitiveUniqueEmails
    result["transitive-leaks"] = transitiveLeaks
    result["transitive-total-leaks"] = transitiveTotalLeaks
    result["transitive-total-viable-leaks"] = transitiveTotalViableLeaks

    printResult(result, "npm")
    return result, response


def getPypiInfo(package):
    response = json.loads(
        requests.get(
            "https://pypi.org/pypi/" + urllib.parse.quote_plus(package) + "/json"
        ).content
    )
    metadata = response["info"]

    result = dict()
    emails = [metadata["maintainer_email"]]
    emails = list(set(filter(None, emails)))

    leaks, totalLeaks, totalViableLeaks, avgLeaks, avgViableLeaks = getLeaks(emails)
    release, maintained = inPastYear(
        response["releases"][metadata["version"]][0]["upload_time"], "%Y-%m-%dT%H:%M:%S"
    )
    dependencies = getPypiDependencies(package, [], True)
    (
        transitiveDependencies,
        transitiveUniqueEmails,
        transitiveLeaks,
        transitiveTotalLeaks,
        transitiveTotalViableLeaks,
    ) = calculateAttackSurface(package, "pypi")

    result["package"] = package
    result["emails"] = emails
    result["last-release"] = str(release)
    result["leaks"] = leaks
    result["total-leaks"] = totalLeaks
    result["total-viable-leaks"] = totalViableLeaks
    result["average-leaks"] = avgLeaks
    result["average-viable-leaks"] = avgViableLeaks
    result["maintained"] = maintained
    result["dependencies"] = dependencies
    result["transitive-dependencies"] = transitiveDependencies
    result["transitive-emails"] = transitiveUniqueEmails
    result["transitive-leaks"] = transitiveLeaks
    result["transitive-total-leaks"] = transitiveTotalLeaks
    result["transitive-total-viable-leaks"] = transitiveTotalViableLeaks

    printResult(result, "pypi")
    return result, response


def getLeaks(emails):
    leaks = dict()
    totalLeaks = 0
    totalViableLeaks = 0
    for email in emails:
        websites = queryHIBP(email)
        viableLeakNum = sum([1 for key in websites if websites[key] == False])
        leaks[email] = {
            "leakNum": len(websites),
            "viableLeakNum": viableLeakNum,
            "leakWebsites": websites,
        }
        totalLeaks += len(websites)
        totalViableLeaks += viableLeakNum
    avgLeaks = totalLeaks / len(emails) if len(emails) else 0.0
    avgViableLeaks = totalViableLeaks / len(emails) if len(emails) else 0.0

    return leaks, totalLeaks, totalViableLeaks, avgLeaks, avgViableLeaks


def queryHIBP(email):
    headers = {"user-agent": "package-analysis", "hibp-api-key": HIBP_V3_TOKEN}
    url = "https://haveibeenpwned.com/api/v3/breachedaccount/"
    response = requests.get(url + urllib.parse.quote_plus(email), headers=headers)
    while response.status_code == 429:
        wait = int(response.headers["retry-after"])
        time.sleep(wait)
        response = requests.get(url + urllib.parse.quote_plus(email), headers=headers)

    if response.content == b"":
        return {}
    response = json.loads(response.content)

    breaches = [breach["Name"] for breach in response]

    result = dict()
    url = "https://haveibeenpwned.com/api/v3/breach/"
    for breach in breaches:
        response = json.loads(
            requests.get(url + urllib.parse.quote_plus(breach), headers=headers).content
        )
        _, viable = inPastYear(response["BreachDate"], "%Y-%m-%d")
        result[breach] = viable

    return result


def calculateAttackSurface(package, packageManager):
    if packageManager not in ["cargo", "npm", "pypi"]:
        return None

    uniqueEmails = set()
    noTransitive = True

    if packageManager == "cargo":
        dependencies = getCargoDependencies(package, [], noTransitive)
        for package in dependencies:
            emails, _ = getCargoEmails(package)
            uniqueEmails.update(emails)
    elif packageManager == "npm":
        dependencies = getNpmDependencies(package, [], noTransitive)
        for package in dependencies:
            response = json.loads(
                requests.get(
                    "https://api.npms.io/v2/package/" + urllib.parse.quote_plus(package)
                ).content
            )
            metadata = response["collected"]["metadata"]

            if "maintainers" in metadata:
                maintainers = metadata["maintainers"]
                for maintainer in maintainers:
                    if "email" in maintainer:
                        email = maintainer["email"]
                        uniqueEmails.add(email)

    elif packageManager == "pypi":
        dependencies = getPypiDependencies(package, [], noTransitive)
        for package in dependencies:
            response = requests.get(
                "https://pypi.org/pypi/" + urllib.parse.quote_plus(package) + "/json"
            )
            if response.status_code == 200:
                response = json.loads(response.content)
                emails = [response["info"]["maintainer_email"]]
                if "" in emails:
                    emails.remove("")
                if None in emails:
                    emails.remove(None)
                uniqueEmails.update(emails)

    leaks, totalLeaks, totalViableLeaks, _, _ = getLeaks(uniqueEmails)

    return dependencies, list(uniqueEmails), leaks, totalLeaks, totalViableLeaks


def getCargoDependencies(package, visited, direct):
    response = json.loads(
        requests.get(
            "https://crates.io/api/v1/crates/" + urllib.parse.quote_plus(package)
        ).content
    )

    latest = response["crate"]["newest_version"]

    response = json.loads(
        requests.get(
            "https://crates.io/api/v1/crates/"
            + urllib.parse.quote_plus(package)
            + "/"
            + urllib.parse.quote_plus(latest)
            + "/dependencies"
        ).content
    )

    if "dependencies" in response and response["dependencies"] != []:
        directDependencies = [
            dependency["crate_id"] for dependency in response["dependencies"]
        ]
        result = directDependencies
        if direct:
            return result
        for dependency in directDependencies:
            if dependency not in visited:
                visited.append(dependency)
                result += getCargoDependencies(dependency, visited, False)
        return list(set(result))
    else:
        return []


def getNpmDependencies(package, visited, direct):
    response = json.loads(
        requests.get(
            "https://registry.npmjs.org/" + urllib.parse.quote_plus(package)
        ).content
    )

    latest = response["dist-tags"]["latest"]

    if (
        "dependencies" in response["versions"][latest]
        and response["versions"][latest]["dependencies"] != {}
    ):
        directDependencies = list(response["versions"][latest]["dependencies"].keys())
        result = directDependencies
        if direct:
            return result
        for dependency in directDependencies:
            if dependency not in visited:
                visited.append(dependency)
                result += getNpmDependencies(dependency, visited, False)
        return list(set(result))
    else:
        return []


def getPypiDependencies(package, visited, direct):
    response = json.loads(
        requests.get(
            "https://pypi.org/pypi/" + urllib.parse.quote_plus(package) + "/json"
        ).content
    )

    if response["info"]["requires_dist"] != None:
        directDependencies = [
            dep.replace(";", " ").split(" ")[0]
            for dep in response["info"]["requires_dist"]
        ]
        result = directDependencies
        if direct:
            return result
        for dependency in directDependencies:
            if dependency not in visited:
                visited.append(dependency)
                result += getPypiDependencies(dependency, visited, False)
        return list(set(result))
    else:
        return []


def inPastYear(date, format):
    release = datetime.datetime.strptime(date, format).replace(
        microsecond=0, tzinfo=None
    )
    if (NOW - release) > datetime.timedelta(days=365):
        return release, False
    else:
        return release, True


def checkCI(repo):
    headers = {"Authorization": "token " + GITHUB_TOKEN}
    response = requests.get(
        "https://api.github.com/repos/" + repo + "/commits/master/status",
        headers=headers,
    )  # fix this if there's already a slash at the end of repo
    response.raise_for_status()
    statuses = response.json()["statuses"]

    result = dict()

    # CI Contexts: ci/circleci, continuous-integration/travis-ci/push
    for status in statuses:
        context = status["context"]
        date = release = datetime.datetime.strptime(
            status["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
        )
        details = {"state": status["state"], "date": date}

        # Only get Travis and CircleCI contexts, as there are others that are not CI checks
        cis = ["ci/circleci", "continuous-integration/travis-ci"]
        for ci in cis:
            if ci in context:
                result[context] = details

    return result


def printResult(result, packageManager):

    output = """
=== {0} ===
Total leaks: {1}
Avg leaks/person: {2}
Last release: {3}
Maintained: {4}
Direct dependencies: {5}
Total dependencies: {6}
Attack Surface: {7}"""
    output = output.format(
        str(result["package"]),
        str(result["total-leaks"]),
        str(result["average-leaks"]),
        str(result["last-release"]),
        str(result["maintained"]),
        str(len(result["dependencies"])),
        str(len(result["transitive-dependencies"])),
        str(result["transitive-total-leaks"]),
    )
    print(output)

    if packageManager != "pypi":
        output = """Source: {0}
Downloads: {1}
Dependents: {2}"""
        output = output.format(
            str(result["source"]), str(result["downloads"]), str(result["dependents"])
        )
        print(output)


main()
