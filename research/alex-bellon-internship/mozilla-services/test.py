import json

a = ["fxa-password-strength-checker"]
b = [
    "fxa-amplitude-send",
    "telemetry-analysis-service",
    "speech-proxy",
    "browserid-verifier",
    "watchdog-proxy",
    "blurts-server",
    "fxa-crypto-relier",
    "fxa-pairing-channel",
    "vpn-recommendation-shield-study",
    "addons-linter",
    "lockwise-addon",
]
c = [
    "eslint-plugin-fxa",
    "fxa-content-server-l10n",
    "fxa-amplitude-send",
    "testpilot",
    "speech-proxy",
    "gecko-dev",
    "gecko-dev-dep-files",
    "browserid-verifier",
    "screenshots-admin",
    "watchdog-proxy",
    "fxa-crypto-relier",
    "fxa-pairing-channel",
    "vpn-recommendation-shield-study",
    "blurts-server",
    "addons-linter",
    "lockwise-addon",
]

# d = ['telemetry-analysis-service', 'taskcluster-tools', 'addons-server']
# e = ['eslint-plugin-fxa', 'fxa-content-server-l10n', 'fxa-amplitude-send', 'fxa-crypto-relier', 'watchdog-proxy', 'vpn-recommendation-shield-study', 'gecko-dev-dep-files', 'testpilot', 'speech-proxy', 'gecko-dev', 'browserid-verifier', 'screenshots-admin', 'fxa-pairing-channel', 'blurts-server', 'addons-linter', 'lockwise-addon']
# f = ['delivery-console', 'eslint-plugin-fxa', 'fxa-content-server-l10n', 'fxa-crypto-relier', 'screenshots-admin', 'watchdog-proxy', 'aws-provisioner', 'azure-blob-storage', 'vpn-recommendation-shield-study', 'azure-entities', 'taskcluster-backup', 'taskcluster', 'ws-shell', 'gecko-dev', 'browserid-verifier', 'fxa-amplitude-send', 'speech-proxy', 'gecko-dev-dep-files', 'fxa-pairing-channel', 'blurts-server', 'addons-linter', 'lockwise-addon']


d = [
    "aws-provisioner",
    "azure-entities",
    "cloud-mirror",
    "dind-service",
    "dockerode-process",
    "fast-azure-storage",
    "browserid-verifier",
    "eslint-plugin-fxa",
    "fxa-amplitude-send",
    "speech-proxy",
    "testpilot",
    "azure-blob-storage",
    "remotely-signed-s3",
    "taskcluster",
    "ws-shell",
    "gecko-dev",
    "gecko-dev-dep-files",
    "screenshots-admin",
    "watchdog-proxy",
    "vpn-recommendation-shield-study",
    "blurts-server",
    "fxa-crypto-relier",
    "fxa-pairing-channel",
    "lockwise-addon",
    "addons-linter",
]
e = [
    "addons-frontend",
    "speech-proxy",
    "azure-entities",
    "taskcluster",
    "browserid-verifier",
    "screenshots-admin",
    "blurts-server",
]
f = [
    "browserid-verifier",
    "blurts-server",
    "fxa-crypto-relier",
    "fxa-pairing-channel",
    "screenshots-admin",
    "watchdog-proxy",
    "vpn-recommendation-shield-study",
    "addons-linter",
    "lockwise-addon",
]
g = ["taskcluster", "vpn-recommendation-shield-study", "lockwise-addon"]
h = ["fxa-crypto-relier", "fxa-pairing-channel", "lockwise-addon"]
j = ["speech-proxy", "browserid-verifier", "screenshots-admin", "blurts-server"]

result = set()

for i in a:
    result.add(i)

for i in b:
    result.add(i)

for i in c:
    result.add(i)

print(len(result))

for i in d:
    result.add(i)

for i in e:
    result.add(i)

for i in f:
    result.add(i)

for i in g:
    result.add(i)

for i in h:
    result.add(i)

for i in j:
    result.add(i)
print(len(result))
