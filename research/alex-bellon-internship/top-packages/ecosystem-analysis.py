import json, pprint


def getData(numPackages):
    cargo = json.loads(
        open(
            "output/top-"
            + str(numPackages)
            + "/cargo-top-"
            + str(numPackages)
            + "-results.json",
            "r",
        ).read()
    )
    npm = json.loads(
        open(
            "output/top-"
            + str(numPackages)
            + "/npm-top-"
            + str(numPackages)
            + "-results.json",
            "r",
        ).read()
    )
    pypi = json.loads(
        open(
            "output/top-"
            + str(numPackages)
            + "/pypi-top-"
            + str(numPackages)
            + "-results.json",
            "r",
        ).read()
    )

    ecosystems = 3

    totalLeaks = 0
    cargoLeaks = 0
    npmLeaks = 0
    pypiLeaks = 0

    totalAvgLeaks = 0
    cargoAvgLeaks = 0
    npmAvgLeaks = 0
    pypiAvgLeaks = 0

    totalMaintained = 0
    cargoMaintained = 0
    npmMaintained = 0
    pypiMaintained = 0

    totalUniqueEmails = dict()
    cargoUniqueEmails = dict()
    npmUniqueEmails = dict()
    pypiUniqueEmails = dict()

    for package in cargo:
        totalLeaks += package["total-leaks"]
        cargoLeaks += package["total-leaks"]
        totalAvgLeaks += package["average-leaks"]
        cargoAvgLeaks += package["average-leaks"]
        totalMaintained += package["maintained"]
        cargoMaintained += package["maintained"]

        emails = package["leaks"].keys()

        for email in emails:
            totalUniqueEmails[email] = package["leaks"][email]["leakNum"]
            cargoUniqueEmails[email] = package["leaks"][email]["leakNum"]

    for package in npm:
        totalLeaks += package["total-leaks"]
        npmLeaks += package["total-leaks"]
        totalAvgLeaks += package["average-leaks"]
        npmAvgLeaks += package["average-leaks"]
        totalMaintained += package["maintained"]
        npmMaintained += package["maintained"]

        emails = package["leaks"].keys()

        for email in emails:
            totalUniqueEmails[email] = package["leaks"][email]["leakNum"]
            npmUniqueEmails[email] = package["leaks"][email]["leakNum"]

    for package in pypi:
        totalLeaks += package["total-leaks"]
        pypiLeaks += package["total-leaks"]
        totalAvgLeaks += package["average-leaks"]
        pypiAvgLeaks += package["average-leaks"]
        totalMaintained += package["maintained"]
        pypiMaintained += package["maintained"]

        emails = package["leaks"].keys()

        for email in emails:
            totalUniqueEmails[email] = package["leaks"][email]["leakNum"]
            pypiUniqueEmails[email] = package["leaks"][email]["leakNum"]

    result = dict()
    result["totalLeaks"] = totalLeaks
    result["cargoLeaks"] = cargoLeaks
    result["npmLeaks"] = npmLeaks
    result["pypiLeaks"] = pypiLeaks

    result["totalAverageLeaks"] = "{:.3}".format(
        totalAvgLeaks / (numPackages * ecosystems)
    )
    result["cargoAverageLeaks"] = "{:.3}".format(cargoAvgLeaks / numPackages)
    result["npmAverageLeaks"] = "{:.3}".format(npmAvgLeaks / numPackages)
    result["pypiAverageLeaks"] = "{:.3}".format(pypiAvgLeaks / numPackages)

    result["totalMaintained"] = "{:.2%}".format(
        totalMaintained / (numPackages * ecosystems)
    )
    result["cargoMaintained"] = "{:.2%}".format(cargoMaintained / numPackages)
    result["npmMaintained"] = "{:.2%}".format(npmMaintained / numPackages)
    result["pypiMaintained"] = "{:.2%}".format(pypiMaintained / numPackages)

    return result


def printResults(data):
    leaks = """|                                | Top 50 | Top 100 | Top 250 | Top 500 |
|--------------------------------|--------|---------|---------|---------|
| Cargo leaks             | {0}    | {1}     | {2}     | {3}    |
| NPM leaks               | {4}    | {5}     | {6}     | {7}    |
| PyPI leaks              | {8}    | {9}     | {10}    | {11}   |
| **Total leaks**         | {12}   | {13}    | {14}    | {15}   |
"""
    leaks = leaks.format(
        str(data[50]["cargoLeaks"]),
        str(data[100]["cargoLeaks"]),
        str(data[250]["cargoLeaks"]),
        str(data[500]["cargoLeaks"]),
        str(data[50]["npmLeaks"]),
        str(data[100]["npmLeaks"]),
        str(data[250]["npmLeaks"]),
        str(data[500]["npmLeaks"]),
        str(data[50]["pypiLeaks"]),
        str(data[100]["pypiLeaks"]),
        str(data[250]["pypiLeaks"]),
        str(data[500]["pypiLeaks"]),
        str(data[50]["totalLeaks"]),
        str(data[100]["totalLeaks"]),
        str(data[250]["totalLeaks"]),
        str(data[500]["totalLeaks"]),
    )

    avgLeaks = """|                               |        |         |         |         |
| Cargo avg leaks/person             | {0}    | {1}     | {2}     | {3}    |
| NPM avg leaks/person               | {4}    | {5}     | {6}     | {7}    |
| PyPI avg leaks/person              | {8}    | {9}     | {10}    | {11}   |
| **Total avg leaks/person**         | {12}   | {13}    | {14}    | {15}   |
"""
    avgLeaks = avgLeaks.format(
        str(data[50]["cargoAverageLeaks"]),
        str(data[100]["cargoAverageLeaks"]),
        str(data[250]["cargoAverageLeaks"]),
        str(data[500]["cargoAverageLeaks"]),
        str(data[50]["npmAverageLeaks"]),
        str(data[100]["npmAverageLeaks"]),
        str(data[250]["npmAverageLeaks"]),
        str(data[500]["npmAverageLeaks"]),
        str(data[50]["pypiAverageLeaks"]),
        str(data[100]["pypiAverageLeaks"]),
        str(data[250]["pypiAverageLeaks"]),
        str(data[500]["pypiAverageLeaks"]),
        str(data[50]["totalAverageLeaks"]),
        str(data[100]["totalAverageLeaks"]),
        str(data[250]["totalAverageLeaks"]),
        str(data[500]["totalAverageLeaks"]),
    )

    maintained = """\n|                                | Top 50 | Top 100 | Top 250 | Top 500 |
|--------------------------------|--------|---------|---------|---------|
| Cargo total maintained package %      | {0}    | {1}     | {2}     | {3}    |
| NPM total maintained package %        | {4}    | {5}     | {6}     | {7}    |
| PyPI total maintained package %       | {8}    | {9}     | {10}    | {11}   |
| **Total total maintained package %**  | {12}   | {13}    | {14}    | {15}   |
"""
    maintained = maintained.format(
        str(data[50]["cargoMaintained"]),
        str(data[100]["cargoMaintained"]),
        str(data[250]["cargoMaintained"]),
        str(data[500]["cargoMaintained"]),
        str(data[50]["npmMaintained"]),
        str(data[100]["npmMaintained"]),
        str(data[250]["npmMaintained"]),
        str(data[500]["npmMaintained"]),
        str(data[50]["pypiMaintained"]),
        str(data[100]["pypiMaintained"]),
        str(data[250]["pypiMaintained"]),
        str(data[500]["pypiMaintained"]),
        str(data[50]["totalMaintained"]),
        str(data[100]["totalMaintained"]),
        str(data[250]["totalMaintained"]),
        str(data[500]["totalMaintained"]),
    )

    print(leaks + avgLeaks + maintained)


def main():
    numPackages = [10, 50, 100, 250, 500]
    data = dict()
    for num in numPackages:
        data[num] = getData(num)
    printResults(data)


main()
