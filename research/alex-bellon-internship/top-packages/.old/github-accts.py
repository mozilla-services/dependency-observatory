import datetime, hashlib, json, pprint, requests, sys, urllib

GITHUB_TOKEN = open("../../github-token.txt").read().strip("\n")

account = "alex-bellon"
headers = {"Authorization": "token " + GITHUB_TOKEN}

orgs = json.loads(
    requests.get(
        "https://api.github.com/users/" + urllib.parse.quote_plus(account) + "/orgs",
        headers=headers,
    ).content
)

for org in orgs:
    response = json.loads(requests.get(org["url"], headers=headers).content)
    # pprint.pprint(response)
    print(response["url"])
    if "two_factor_requirement_enabled" in response:
        pprint.pprint(response["two_factor_requirement_enabled"])

query = """
{
  organization (login: "UTISSS") {
    requiresTwoFactorAuthentication
  }
}
"""
response = requests.post(
    "https://api.github.com/graphql", json={"query": query}, headers=headers
)
print(response)
