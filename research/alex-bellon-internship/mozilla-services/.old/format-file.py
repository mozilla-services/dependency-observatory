import json, pprint

file = open("dependency-metadata.jsonl")
projects = [json.loads(line) for line in file.read().splitlines()]

npmPackages = dict()
pypiPackages = dict()

for project in projects:
    if (
        project["repository"] != None
        and "dependencyGraphManifests" in project["repository"]
    ):
        projectName = project["repository"]["name"]
        graph = project["repository"]["dependencyGraphManifests"]["edges"]
        if len(graph):
            nodes = graph[0]["node"]["dependencies"]["nodes"]
            for node in nodes:
                packageManager = node["packageManager"]
                packageName = node["packageName"]
                if packageManager == "NPM":
                    if packageName not in npmPackages:
                        npmPackages[packageName] = []
                    list = npmPackages[packageName]
                    if projectName not in list:
                        list.append(projectName)
                    npmPackages[packageName] = list
                if packageManager == "PIP":
                    if packageName not in pypiPackages:
                        pypiPackages[packageName] = []
                    list = pypiPackages[packageName]
                    if projectName not in list:
                        list.append(projectName)
                    pypiPackages[packageName] = list

npmOutput = open("npm-packages.json", "w")
npmOutput.write(json.dumps(npmPackages))

pypiOutput = open("pypi-packages.json", "w")
pypiOutput.write(json.dumps(pypiPackages))
