import logging

from flask import current_app
import requests

from depobs.database.models import save_json_results


log = logging.getLogger(__name__)


def get_github_advisories_for_package(package_name: str) -> None:

    github_client = current_app.config["GITHUB_CLIENT"]
    base_url = github_client["base_url"]
    github_auth_token = github_client["github_auth_token"]

    headers = {"Authorization": "token " + github_auth_token}

    query = f"""
    {{
        securityVulnerabilities(ecosystem: NPM, first: 100, package: \"{package_name}\", orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
            nodes {{
                advisory {{
                    id, description, permalink, publishedAt, severity, summary, updatedAt, withdrawnAt
                }}
                package {{
                    name
                }}
            }}
            pageInfo {{
                endCursor, hasNextPage, hasPreviousPage, startCursor
            }}
            totalCount
        }}
    }}
    """

    response = requests.post(base_url, json={"query": query}, headers=headers)
    response.raise_for_status()
    nodes = response.json()["data"]["securityVulnerabilities"]["nodes"]

    advisories = list()
    ids = list()
    for node in nodes:
        if (
            node["advisory"]["id"] not in ids
            and node["advisory"]["withdrawnAt"] == None
        ):
            advisory = node["advisory"]
            advisory["package"] = package_name
            advisories.append(advisory)
            ids.append(node["advisory"]["id"])

    save_json_results(advisories)


def get_github_advisories() -> None:

    github_client = current_app.config["GITHUB_CLIENT"]
    base_url = github_client["base_url"]
    github_auth_token = github_client["github_auth_token"]

    headers = {"Authorization": "token " + github_auth_token}

    perPage = 100

    query = f"""
    {{
        securityVulnerabilities(ecosystem: NPM, first: {perPage}, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
            nodes {{
                advisory {{
                    id, description, permalink, publishedAt, severity, summary, updatedAt, withdrawnAt
                }}
                package {{
                    name
                }}
            }}
            pageInfo {{
                endCursor, hasNextPage, hasPreviousPage, startCursor
            }}
            totalCount
        }}
    }}
    """

    response = requests.post(base_url, json={"query": query}, headers=headers)
    response.raise_for_status()
    response_json = response.json()["data"]["securityVulnerabilities"]

    nodes = response_json["nodes"]
    hasNextPage = response_json["pageInfo"]["hasNextPage"]
    endCursor = response_json["pageInfo"]["endCursor"]

    while hasNextPage:
        query = f"""
        {{
            securityVulnerabilities(ecosystem: NPM, first: {perPage}, after: \"{endCursor}\", orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
                nodes {{
                    advisory {{
                        id, description, permalink, publishedAt, severity, summary, updatedAt, withdrawnAt
                    }}
                    package {{
                        name
                    }}
                }}
                pageInfo {{
                    endCursor, hasNextPage, hasPreviousPage, startCursor
                }}
                totalCount
            }}
        }}
        """

        response = requests.post(base_url, json={"query": query}, headers=headers)
        response.raise_for_status()
        response_json = response.json()["data"]["securityVulnerabilities"]

        nodes += response_json["nodes"]
        hasNextPage = response_json["pageInfo"]["hasNextPage"]
        endCursor = response_json["pageInfo"]["endCursor"]

    advisories = list()
    ids = list()
    for node in nodes:
        if (
            node["advisory"]["id"] not in ids
            and node["advisory"]["withdrawnAt"] == None
        ):
            advisory = node["advisory"]
            advisories.append(advisory)
            ids.append(node["advisory"]["id"])

    save_json_results(advisories)
