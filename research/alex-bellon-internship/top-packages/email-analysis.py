import json, pprint


def main():
    numPackages = ["50", "100", "250", "500"]
    results = dict()
    for num in numPackages:
        results[num] = getEmails(num)

    printResults(results)
    output = open("output/email-results.json", "w")
    output.write(json.dumps(results))


def getEmails(numPackages):
    cargo = json.loads(
        open(
            "output/top-" + numPackages + "/cargo-top-" + numPackages + "-results.json",
            "r",
        ).read()
    )
    npm = json.loads(
        open(
            "output/top-" + numPackages + "/npm-top-" + numPackages + "-results.json",
            "r",
        ).read()
    )
    pypi = json.loads(
        open(
            "output/top-" + numPackages + "/pypi-top-" + numPackages + "-results.json",
            "r",
        ).read()
    )

    totalUniqueEmails = dict()
    cargoUniqueEmails = dict()
    npmUniqueEmails = dict()
    pypiUniqueEmails = dict()

    for package in cargo:
        emails = package["leaks"].keys()
        for email in emails:
            totalUniqueEmails[email] = package["leaks"][email]["leakNum"]
            cargoUniqueEmails[email] = package["leaks"][email]["leakNum"]

    for package in npm:
        emails = package["leaks"].keys()
        for email in emails:
            totalUniqueEmails[email] = package["leaks"][email]["leakNum"]
            npmUniqueEmails[email] = package["leaks"][email]["leakNum"]

    for package in pypi:
        emails = package["leaks"].keys()
        for email in emails:
            totalUniqueEmails[email] = package["leaks"][email]["leakNum"]
            pypiUniqueEmails[email] = package["leaks"][email]["leakNum"]

    sortedTotalEmails = {
        email: leaks
        for email, leaks in sorted(
            totalUniqueEmails.items(), key=lambda x: x[1], reverse=True
        )
    }
    sortedCargoEmails = {
        email: leaks
        for email, leaks in sorted(
            cargoUniqueEmails.items(), key=lambda x: x[1], reverse=True
        )
    }
    sortedNpmEmails = {
        email: leaks
        for email, leaks in sorted(
            npmUniqueEmails.items(), key=lambda x: x[1], reverse=True
        )
    }
    sortedPypiEmails = {
        email: leaks
        for email, leaks in sorted(
            pypiUniqueEmails.items(), key=lambda x: x[1], reverse=True
        )
    }

    cargoResult = categorizeEmails(sortedCargoEmails, "Cargo")
    npmResult = categorizeEmails(sortedNpmEmails, "NPM")
    pypiResult = categorizeEmails(sortedPypiEmails, "PyPI")
    totalResult = categorizeEmails(sortedTotalEmails, "Total")

    return {
        "cargo": cargoResult,
        "npm": npmResult,
        "pypi": pypiResult,
        "total": totalResult,
    }


def categorizeEmails(dict, name):
    gmail = list()
    edu = list()
    gov = list()
    other = list()
    leaks = 0

    for email in dict.keys():
        if dict[email]:  # Has at least one leak
            if "gmail.com" in email:
                gmail.append(email)
            elif ".edu" in email:
                edu.append(email)
            elif ".gov" in email:
                gov.append(email)
            else:
                other.append(email)
            leaks += 1

    result = {
        "users": len(dict),
        "users-with-leaks": leaks,
        "gmail": gmail,
        "edu": edu,
        "gov": gov,
        "other": other,
    }

    return result


def printResults(data):
    cargoResult = """|                               | Top 50 | Top 100 | Top 250 | Top 500 |
|-------------------------------|--------|---------|---------|---------|
| Cargo users with >0 leaks     | {0}    | {1}     | {2}     | {3}     |
| Cargo users                   | {4}    | {5}     | {6}     | {7}     |
"""
    cargoResult = cargoResult.format(
        str(data["50"]["cargo"]["users-with-leaks"]),
        str(data["100"]["cargo"]["users-with-leaks"]),
        str(data["250"]["cargo"]["users-with-leaks"]),
        str(data["500"]["cargo"]["users-with-leaks"]),
        str(data["50"]["cargo"]["users"]),
        str(data["100"]["cargo"]["users"]),
        str(data["250"]["cargo"]["users"]),
        str(data["500"]["cargo"]["users"]),
    )

    npmResult = """|                               |        |         |         |         |
| NPM users with >0 leaks       | {0}    | {1}     | {2}     | {3}     |
| NPM users                     | {4}    | {5}     | {6}     | {7}     |
"""
    npmResult = npmResult.format(
        str(data["50"]["npm"]["users-with-leaks"]),
        str(data["100"]["npm"]["users-with-leaks"]),
        str(data["250"]["npm"]["users-with-leaks"]),
        str(data["500"]["npm"]["users-with-leaks"]),
        str(data["50"]["npm"]["users"]),
        str(data["100"]["npm"]["users"]),
        str(data["250"]["npm"]["users"]),
        str(data["500"]["npm"]["users"]),
    )

    pypiResult = """|                               |        |         |         |         |
| PyPI users with >0 leaks      | {0}    | {1}     | {2}     | {3}     |
| PyPI users                    | {4}    | {5}     | {6}     | {7}     |
"""
    pypiResult = pypiResult.format(
        str(data["50"]["pypi"]["users-with-leaks"]),
        str(data["100"]["pypi"]["users-with-leaks"]),
        str(data["250"]["pypi"]["users-with-leaks"]),
        str(data["500"]["pypi"]["users-with-leaks"]),
        str(data["50"]["pypi"]["users"]),
        str(data["100"]["pypi"]["users"]),
        str(data["250"]["pypi"]["users"]),
        str(data["500"]["pypi"]["users"]),
    )

    totalResult = """|                               |        |         |         |         |
| **Total users with >0 leaks** | {0}    | {1}     | {2}     | {3}     |
| **Total users**               | {4}    | {5}     | {6}     | {7}     |
"""
    totalResult = totalResult.format(
        str(data["50"]["total"]["users-with-leaks"]),
        str(data["100"]["total"]["users-with-leaks"]),
        str(data["250"]["total"]["users-with-leaks"]),
        str(data["500"]["total"]["users-with-leaks"]),
        str(data["50"]["total"]["users"]),
        str(data["100"]["total"]["users"]),
        str(data["250"]["total"]["users"]),
        str(data["500"]["total"]["users"]),
    )

    print(cargoResult + npmResult + pypiResult + totalResult)

    gmailResult = """|                                | Top 50 | Top 100 | Top 250 | Top 500 |
|--------------------------------|--------|---------|---------|---------|
| Cargo Gmail emails             | {0}    | {1}     | {2}     | {3}    |
| NPM Gmail emails               | {4}    | {5}     | {6}     | {7}    |
| PyPI Gmail emails              | {8}    | {9}     | {10}    | {11}   |
| **Total Gmail emails**         | {12}   | {13}    | {14}    | {15}   |
"""
    gmailResult = gmailResult.format(
        str(len(data["50"]["cargo"]["gmail"])),
        str(len(data["100"]["cargo"]["gmail"])),
        str(len(data["250"]["cargo"]["gmail"])),
        str(len(data["500"]["cargo"]["gmail"])),
        str(len(data["50"]["npm"]["gmail"])),
        str(len(data["100"]["npm"]["gmail"])),
        str(len(data["250"]["npm"]["gmail"])),
        str(len(data["500"]["npm"]["gmail"])),
        str(len(data["50"]["pypi"]["gmail"])),
        str(len(data["100"]["pypi"]["gmail"])),
        str(len(data["250"]["pypi"]["gmail"])),
        str(len(data["500"]["pypi"]["gmail"])),
        str(len(data["50"]["total"]["gmail"])),
        str(len(data["100"]["total"]["gmail"])),
        str(len(data["250"]["total"]["gmail"])),
        str(len(data["500"]["total"]["gmail"])),
    )

    eduResult = """|                                |        |         |         |         |
| Cargo .edu emails             | {0}    | {1}     | {2}     | {3}    |
| NPM .edu emails               | {4}    | {5}     | {6}     | {7}    |
| PyPI .edu emails              | {8}    | {9}     | {10}    | {11}   |
| **Total .edu emails**         | {12}   | {13}    | {14}    | {15}   |
"""
    eduResult = eduResult.format(
        str(len(data["50"]["cargo"]["edu"])),
        str(len(data["100"]["cargo"]["edu"])),
        str(len(data["250"]["cargo"]["edu"])),
        str(len(data["500"]["cargo"]["edu"])),
        str(len(data["50"]["npm"]["edu"])),
        str(len(data["100"]["npm"]["edu"])),
        str(len(data["250"]["npm"]["edu"])),
        str(len(data["500"]["npm"]["edu"])),
        str(len(data["50"]["pypi"]["edu"])),
        str(len(data["100"]["pypi"]["edu"])),
        str(len(data["250"]["pypi"]["edu"])),
        str(len(data["500"]["pypi"]["edu"])),
        str(len(data["50"]["total"]["edu"])),
        str(len(data["100"]["total"]["edu"])),
        str(len(data["250"]["total"]["edu"])),
        str(len(data["500"]["total"]["edu"])),
    )

    govResult = """|                                |        |         |         |         |
| Cargo .gov emails             | {0}    | {1}     | {2}     | {3}    |
| NPM .gov emails               | {4}    | {5}     | {6}     | {7}    |
| PyPI .gov emails              | {8}    | {9}     | {10}    | {11}   |
| **Total .gov emails**         | {12}   | {13}    | {14}    | {15}   |
"""
    govResult = govResult.format(
        str(len(data["50"]["cargo"]["gov"])),
        str(len(data["100"]["cargo"]["gov"])),
        str(len(data["250"]["cargo"]["gov"])),
        str(len(data["500"]["cargo"]["gov"])),
        str(len(data["50"]["npm"]["gov"])),
        str(len(data["100"]["npm"]["gov"])),
        str(len(data["250"]["npm"]["gov"])),
        str(len(data["500"]["npm"]["gov"])),
        str(len(data["50"]["pypi"]["gov"])),
        str(len(data["100"]["pypi"]["gov"])),
        str(len(data["250"]["pypi"]["gov"])),
        str(len(data["500"]["pypi"]["gov"])),
        str(len(data["50"]["total"]["gov"])),
        str(len(data["100"]["total"]["gov"])),
        str(len(data["250"]["total"]["gov"])),
        str(len(data["500"]["total"]["gov"])),
    )

    otherResult = """|                                |        |         |         |         |
| Cargo other emails             | {0}    | {1}     | {2}     | {3}    |
| NPM other emails               | {4}    | {5}     | {6}     | {7}    |
| PyPI other emails              | {8}    | {9}     | {10}    | {11}   |
| **Total other emails**         | {12}   | {13}    | {14}    | {15}   |
"""
    otherResult = otherResult.format(
        str(len(data["50"]["cargo"]["other"])),
        str(len(data["100"]["cargo"]["other"])),
        str(len(data["250"]["cargo"]["other"])),
        str(len(data["500"]["cargo"]["other"])),
        str(len(data["50"]["npm"]["other"])),
        str(len(data["100"]["npm"]["other"])),
        str(len(data["250"]["npm"]["other"])),
        str(len(data["500"]["npm"]["other"])),
        str(len(data["50"]["pypi"]["other"])),
        str(len(data["100"]["pypi"]["other"])),
        str(len(data["250"]["pypi"]["other"])),
        str(len(data["500"]["pypi"]["other"])),
        str(len(data["50"]["total"]["other"])),
        str(len(data["100"]["total"]["other"])),
        str(len(data["250"]["total"]["other"])),
        str(len(data["500"]["total"]["other"])),
    )

    print(gmailResult + eduResult + govResult + otherResult)


main()
