import itertools
import json
import pathlib
from typing import Any, Dict, List

import pytest

import depobs.worker.serializers as m


def load_json_fixture(path: str) -> Dict[str, Any]:
    with open(path, "r") as fin:
        return json.load(fin)


npm_entry_fixture_paths = sorted(
    (
        pathlib.Path(__file__).parent / ".." / "fixtures" / "nodejs" / "npm_registry"
    ).glob("*.json")
)


@pytest.mark.parametrize(
    "entry_json_path",
    npm_entry_fixture_paths,
    ids=sorted([p.stem for p in npm_entry_fixture_paths]),
)
@pytest.mark.unit
def test_npm_registry_entries_deserialize(entry_json_path: pathlib.Path):
    json_entry = load_json_fixture(entry_json_path)
    serialized = list(m.serialize_npm_registry_entries([json_entry]))
    assert len(serialized) == len(json_entry["versions"].keys())


deserialize_pubsub_test_cases = {
    "hapi-bounce-2.0.0-no-vulns": (
        [
            m.JSONResult(**d)
            for d in [
                {"id": "3"},  # ignore invalid results
                {
                    "id": "24",
                    "inserted_at": "2020-07-23 22:12:19.07709",
                    "data": {
                        "id": "452635538950130",
                        "size": 4325,
                        "type": "google.cloud.pubsub_v1.types.PubsubMessage",
                        "attributes": {"JOB_NAME": "scan-tarball-url-a8905acc"},
                        "publish_time": '"Thu, 23 Jul 2020 22:12:17 GMT"',
                        "data": [
                            {
                                "name": "write_manifest",
                                "type": "task_result",
                                "stderr": "",
                                "stdout": '{"dependencies":{"@hapi/bounce":"2.0.0"}}',
                                "command": 'jq -cnM --arg name "@hapi/bounce" --arg version "2.0.0" \'{dependencies: {}} | .dependencies[$name] = $version\' | tee -a package.json',
                                "versions": {
                                    "jq": "jq-1.5-1-a5b5cbe",
                                    "rg": "ripgrep 0.10.0\n-SIMD -AVX (compiled)\n+SIMD +AVX (runtime)",
                                    "git": "git version 2.20.1",
                                    "npm": "6.14.5",
                                    "nodejs": "v12.18.2",
                                },
                                "exit_code": 0,
                                "envvar_args": {
                                    "LANGUAGE": "nodejs",
                                    "BUILD_TARGET": "",
                                    "PACKAGE_NAME": "@hapi/bounce",
                                    "INSTALL_TARGET": ".",
                                    "PACKAGE_MANAGER": "npm",
                                    "PACKAGE_VERSION": "2.0.0",
                                },
                                "working_dir": "/home/app",
                            },
                            {
                                "name": "install",
                                "type": "task_result",
                                "stderr": "npm notice created a lockfile as package-lock.json. You should commit this file.\nnpm WARN app No description\nnpm WARN app No repository field.\nnpm WARN app No license field.",
                                "stdout": "added 3 packages and audited 3 packages in 0.857s\nfound 0 vulnerabilities",
                                "command": "npm install --save=true .",
                                "versions": {
                                    "jq": "jq-1.5-1-a5b5cbe",
                                    "rg": "ripgrep 0.10.0\n-SIMD -AVX (compiled)\n+SIMD +AVX (runtime)",
                                    "git": "git version 2.20.1",
                                    "npm": "6.14.5",
                                    "nodejs": "v12.18.2",
                                },
                                "exit_code": 0,
                                "envvar_args": {
                                    "LANGUAGE": "nodejs",
                                    "BUILD_TARGET": "",
                                    "PACKAGE_NAME": "@hapi/bounce",
                                    "INSTALL_TARGET": ".",
                                    "PACKAGE_MANAGER": "npm",
                                    "PACKAGE_VERSION": "2.0.0",
                                },
                                "working_dir": "/home/app",
                            },
                            {
                                "name": "list_metadata",
                                "type": "task_result",
                                "stderr": "",
                                "stdout": '{\n  "dependencies": {\n    "@hapi/bounce": {\n      "version": "2.0.0",\n      "from": "@hapi/bounce@2.0.0",\n      "resolved": "https://registry.npmjs.org/@hapi/bounce/-/bounce-2.0.0.tgz",\n      "dependencies": {\n        "@hapi/boom": {\n          "version": "9.1.0",\n          "from": "@hapi/boom@9.x.x",\n          "resolved": "https://registry.npmjs.org/@hapi/boom/-/boom-9.1.0.tgz",\n          "dependencies": {\n            "@hapi/hoek": {\n              "version": "9.0.4",\n              "from": "@hapi/hoek@9.x.x",\n              "resolved": "https://registry.npmjs.org/@hapi/hoek/-/hoek-9.0.4.tgz"\n            }\n          }\n        },\n        "@hapi/hoek": {\n          "version": "9.0.4",\n          "from": "@hapi/hoek@9.x.x",\n          "resolved": "https://registry.npmjs.org/@hapi/hoek/-/hoek-9.0.4.tgz"\n        }\n      }\n    }\n  }\n}',
                                "command": "npm list --json",
                                "versions": {
                                    "jq": "jq-1.5-1-a5b5cbe",
                                    "rg": "ripgrep 0.10.0\n-SIMD -AVX (compiled)\n+SIMD +AVX (runtime)",
                                    "git": "git version 2.20.1",
                                    "npm": "6.14.5",
                                    "nodejs": "v12.18.2",
                                },
                                "exit_code": 0,
                                "envvar_args": {
                                    "LANGUAGE": "nodejs",
                                    "BUILD_TARGET": "",
                                    "PACKAGE_NAME": "@hapi/bounce",
                                    "INSTALL_TARGET": ".",
                                    "PACKAGE_MANAGER": "npm",
                                    "PACKAGE_VERSION": "2.0.0",
                                },
                                "working_dir": "/home/app",
                            },
                            {
                                "name": "audit",
                                "type": "task_result",
                                "stderr": "",
                                "stdout": '{\n  "actions": [],\n  "advisories": {},\n  "muted": [],\n  "metadata": {\n    "vulnerabilities": {\n      "info": 0,\n      "low": 0,\n      "moderate": 0,\n      "high": 0,\n      "critical": 0\n    },\n    "dependencies": 3,\n    "devDependencies": 0,\n    "optionalDependencies": 0,\n    "totalDependencies": 3\n  },\n  "runId": "36e915fd-2754-4a16-922f-19479aac1f8e"\n}',
                                "command": "npm audit --json",
                                "versions": {
                                    "jq": "jq-1.5-1-a5b5cbe",
                                    "rg": "ripgrep 0.10.0\n-SIMD -AVX (compiled)\n+SIMD +AVX (runtime)",
                                    "git": "git version 2.20.1",
                                    "npm": "6.14.5",
                                    "nodejs": "v12.18.2",
                                },
                                "exit_code": 0,
                                "envvar_args": {
                                    "LANGUAGE": "nodejs",
                                    "BUILD_TARGET": "",
                                    "PACKAGE_NAME": "@hapi/bounce",
                                    "INSTALL_TARGET": ".",
                                    "PACKAGE_MANAGER": "npm",
                                    "PACKAGE_VERSION": "2.0.0",
                                },
                                "working_dir": "/home/app",
                            },
                            {"type": "task_complete"},
                        ],
                    },
                },
            ]
        ],
        [
            m.PackageVersion(name="@hapi/hoek", version="9.0.4"),
            m.PackageVersion(name="@hapi/boom", version="9.1.0"),
            m.PackageVersion(name="@hapi/hoek", version="9.0.4"),
            m.PackageVersion(name="@hapi/hoek", version="9.0.4"),
            m.PackageVersion(name="@hapi/bounce", version="2.0.0"),
            m.PackageVersion(name="@hapi/boom", version="9.1.0"),
            m.PackageVersion(name="@hapi/hoek", version="9.0.4"),
            # graph, root package version, and links
            (
                m.PackageGraph(),
                m.PackageVersion(name="@hapi/bounce", version="2.0.0"),
                [
                    (
                        m.PackageVersion(name="@hapi/boom", version="9.1.0"),
                        m.PackageVersion(name="@hapi/hoek", version="9.0.4"),
                    ),
                    (
                        m.PackageVersion(name="@hapi/bounce", version="2.0.0"),
                        m.PackageVersion(name="@hapi/boom", version="9.1.0"),
                    ),
                    (
                        m.PackageVersion(name="@hapi/bounce", version="2.0.0"),
                        m.PackageVersion(name="@hapi/hoek", version="9.0.4"),
                    ),
                ],
            ),
        ],
    ),
    "moz-ssl-config-generator-audit-output": (
        [
            m.JSONResult(**d)
            for d in [
                {
                    "id": "24",
                    "inserted_at": "2020-07-23 22:12:19.07709",
                    "data": {
                        "id": "455069043282785",
                        "publish_time": "Tue, 25 Aug 2020 21:22:32 GMT",
                        "size": 1135990,
                        "type": "google.cloud.pubsub_v1.types.PubsubMessage",
                        "attributes": {
                            "JOB_NAME": "scan-3-depfiles-3f9e6fab",
                            "SCAN_ID": "3",
                        },
                        "data": [
                            {
                                "command": "npm audit --json",
                                "envvar_args": {
                                    "BUILD_TARGET": "",
                                    "INSTALL_TARGET": ".",
                                    "LANGUAGE": "nodejs",
                                    "PACKAGE_MANAGER": "npm",
                                    "PACKAGE_NAME": "",
                                    "PACKAGE_VERSION": "",
                                },
                                "exit_code": 1,
                                "name": "audit",
                                "stderr": "",
                                "stdout": '{\n  "actions": [\n    {\n      "isMajor": true,\n      "action": "install",\n      "resolves": [\n        {\n          "id": 1426,\n          "path": "copy-webpack-plugin\u003eserialize-javascript",\n          "dev": true,\n          "optional": false,\n          "bundled": false\n        },\n        {\n          "id": 1548,\n          "path": "copy-webpack-plugin\u003eserialize-javascript",\n          "dev": true,\n          "optional": false,\n          "bundled": false\n        }\n      ],\n      "module": "copy-webpack-plugin",\n      "target": "6.0.3"\n    },\n    {\n      "action": "update",\n      "resolves": [\n        {\n          "id": 1179,\n          "path": "extract-loader\u003ebabel-plugin-add-module-exports\u003echokidar\u003efsevents\u003enode-pre-gyp\u003emkdirp\u003eminimist",\n          "dev": true,\n          "optional": true,\n          "bundled": true\n        },\n        {\n          "id": 1179,\n          "path": "extract-loader\u003ebabel-plugin-add-module-exports\u003echokidar\u003efsevents\u003enode-pre-gyp\u003etar\u003emkdirp\u003eminimist",\n          "dev": true,\n          "optional": true,\n          "bundled": true\n        },\n        {\n          "id": 1179,\n          "path": "extract-loader\u003ebabel-plugin-add-module-exports\u003echokidar\u003efsevents\u003enode-pre-gyp\u003erc\u003eminimist",\n          "dev": true,\n          "optional": true,\n          "bundled": true\n        }\n      ],\n      "module": null,\n      "target": null,\n      "depth": 3\n    },\n    {\n      "action": "review",\n      "module": "minimist",\n      "resolves": [\n        {\n          "id": 1179,\n          "path": "webpack\u003ewatchpack\u003ewatchpack-chokidar2\u003echokidar\u003efsevents\u003enode-pre-gyp\u003emkdirp\u003eminimist",\n          "dev": true,\n          "optional": true,\n          "bundled": true\n        },\n        {\n          "id": 1179,\n          "path": "webpack\u003ewatchpack\u003ewatchpack-chokidar2\u003echokidar\u003efsevents\u003enode-pre-gyp\u003etar\u003emkdirp\u003eminimist",\n          "dev": true,\n          "optional": true,\n          "bundled": true\n        },\n        {\n          "id": 1179,\n          "path": "webpack\u003ewatchpack\u003ewatchpack-chokidar2\u003echokidar\u003efsevents\u003enode-pre-gyp\u003erc\u003eminimist",\n          "dev": true,\n          "optional": true,\n          "bundled": true\n        }\n      ]\n    }\n  ],\n  "advisories": {\n    "1179": {\n      "findings": [\n        {\n          "version": "0.0.8",\n          "paths": [\n            "extract-loader\u003ebabel-plugin-add-module-exports\u003echokidar\u003efsevents\u003enode-pre-gyp\u003emkdirp\u003eminimist",\n            "webpack\u003ewatchpack\u003ewatchpack-chokidar2\u003echokidar\u003efsevents\u003enode-pre-gyp\u003emkdirp\u003eminimist",\n            "extract-loader\u003ebabel-plugin-add-module-exports\u003echokidar\u003efsevents\u003enode-pre-gyp\u003etar\u003emkdirp\u003eminimist",\n            "webpack\u003ewatchpack\u003ewatchpack-chokidar2\u003echokidar\u003efsevents\u003enode-pre-gyp\u003etar\u003emkdirp\u003eminimist"\n          ]\n        },\n        {\n          "version": "1.2.0",\n          "paths": [\n            "extract-loader\u003ebabel-plugin-add-module-exports\u003echokidar\u003efsevents\u003enode-pre-gyp\u003erc\u003eminimist",\n            "webpack\u003ewatchpack\u003ewatchpack-chokidar2\u003echokidar\u003efsevents\u003enode-pre-gyp\u003erc\u003eminimist"\n          ]\n        }\n      ],\n      "id": 1179,\n      "created": "2019-09-23T15:01:43.049Z",\n      "updated": "2020-03-18T19:41:45.921Z",\n      "deleted": null,\n      "title": "Prototype Pollution",\n      "found_by": {\n        "link": "https://www.checkmarx.com/resources/blog/",\n        "name": "Checkmarx Research Team",\n        "email": ""\n      },\n      "reported_by": {\n        "link": "https://www.checkmarx.com/resources/blog/",\n        "name": "Checkmarx Research Team",\n        "email": ""\n      },\n      "module_name": "minimist",\n      "cves": [],\n      "vulnerable_versions": "\u003c0.2.1 || \u003e=1.0.0 \u003c1.2.3",\n      "patched_versions": "\u003e=0.2.1 \u003c1.0.0 || \u003e=1.2.3",\n      "overview": "Affected versions of `minimist` are vulnerable to prototype pollution. Arguments are not properly sanitized, allowing an attacker to modify the prototype of `Object`, causing the addition or modification of an existing property that will exist on all objects.  \\nParsing the argument `--__proto__.y=Polluted` adds a `y` property with value `Polluted` to all objects. The argument `--__proto__=Polluted` raises and uncaught error and crashes the application.  \\nThis is exploitable if attackers have control over the arguments being passed to `minimist`.\\n",\n      "recommendation": "Upgrade to versions 0.2.1, 1.2.3 or later.",\n      "references": "- [GitHub commit 1](https://github.com/substack/minimist/commit/4cf1354839cb972e38496d35e12f806eea92c11f#diff-a1e0ee62c91705696ddb71aa30ad4f95)\\n- [GitHub commit 2](https://github.com/substack/minimist/commit/63e7ed05aa4b1889ec2f3b196426db4500cbda94)",\n      "access": "public",\n      "severity": "low",\n      "cwe": "CWE-471",\n      "metadata": {\n        "module_type": "",\n        "exploitability": 1,\n        "affected_components": ""\n      },\n      "url": "https://npmjs.com/advisories/1179"\n    },\n    "1426": {\n      "findings": [\n        {\n          "version": "1.7.0",\n          "paths": [\n            "copy-webpack-plugin\u003eserialize-javascript"\n          ]\n        }\n      ],\n      "id": 1426,\n      "created": "2019-12-09T15:26:05.019Z",\n      "updated": "2019-12-10T19:05:13.433Z",\n      "deleted": null,\n      "title": "Cross-Site Scripting",\n      "found_by": {\n        "link": "https://twitter.com/okuryu",\n        "name": "Ryuichi Okumura",\n        "email": ""\n      },\n      "reported_by": {\n        "link": "https://twitter.com/okuryu",\n        "name": "Ryuichi Okumura",\n        "email": ""\n      },\n      "module_name": "serialize-javascript",\n      "cves": [\n        "CVE-2019-16769"\n      ],\n      "vulnerable_versions": "\u003c2.1.1",\n      "patched_versions": "\u003e=2.1.1",\n      "overview": "Versions of `serialize-javascript` prior to 2.1.1 are vulnerable to Cross-Site Scripting (XSS). The package fails to sanitize serialized regular expressions. This vulnerability does not affect Node.js applications.",\n      "recommendation": "Upgrade to version 2.1.1 or later.",\n      "references": "- [GitHub advisory](https://github.com/yahoo/serialize-javascript/security/advisories/GHSA-h9rv-jmmf-4pgx)",\n      "access": "public",\n      "severity": "moderate",\n      "cwe": "CWE-79",\n      "metadata": {\n        "module_type": "",\n        "exploitability": 3,\n        "affected_components": ""\n      },\n      "url": "https://npmjs.com/advisories/1426"\n    },\n    "1548": {\n      "findings": [\n        {\n          "version": "1.7.0",\n          "paths": [\n            "copy-webpack-plugin\u003eserialize-javascript"\n          ]\n        }\n      ],\n      "id": 1548,\n      "created": "2020-08-11T17:27:06.358Z",\n      "updated": "2020-08-11T17:29:23.710Z",\n      "deleted": null,\n      "title": "Remote Code Execution",\n      "found_by": {\n        "link": "",\n        "name": "Unknown",\n        "email": ""\n      },\n      "reported_by": {\n        "link": "",\n        "name": "Unknown",\n        "email": ""\n      },\n      "module_name": "serialize-javascript",\n      "cves": [],\n      "vulnerable_versions": "\u003c3.1.0",\n      "patched_versions": "\u003e=3.1.0",\n      "overview": "`serialize-javascript` prior to 3.1.0 allows remote attackers to inject arbitrary code via the function \\"deleteFunctions\\" within \\"index.js\\".  \\n\\nAn object such as `{\\"foo\\": /1\\"/, \\"bar\\": \\"a\\\\\\"@__R-\u003cUID\u003e-0__@\\"}` was serialized as `{\\"foo\\": /1\\"/, \\"bar\\": \\"a\\\\/1\\"/}`, which allows an attacker to escape the bar key. This requires the attacker to control the values of both foo and bar and guess the value of \u003cUID\u003e. The UID has a keyspace of approximately 4 billion making it a realistic network attack.  \\n  \\nThe following proof-of-concept calls console.log() when the running eval():  \\n`eval(\u0027(\u0027+ serialize({\\"foo\\": /1\\" + console.log(1)/i, \\"bar\\": \u0027\\"@__R-\u003cUID\u003e-0__@\u0027}) + \u0027)\u0027);`",\n      "recommendation": "Upgrade to version 3.1.0 or later.",\n      "references": "- [GitHub Advisory](https://github.com/advisories/GHSA-hxcc-f52p-wc94)",\n      "access": "public",\n      "severity": "high",\n      "cwe": "CWE-",\n      "metadata": {\n        "module_type": "",\n        "exploitability": 4,\n        "affected_components": ""\n      },\n      "url": "https://npmjs.com/advisories/1548"\n    }\n  },\n  "muted": [],\n  "metadata": {\n    "vulnerabilities": {\n      "info": 0,\n      "low": 6,\n      "moderate": 1,\n      "high": 1,\n      "critical": 0\n    },\n    "dependencies": 15,\n    "devDependencies": 1257,\n    "optionalDependencies": 193,\n    "totalDependencies": 1274\n  },\n  "runId": "a7f90c57-b2da-4568-a211-48c9f6facf86"\n}\n',
                                "type": "task_result",
                                "versions": {
                                    "git": "git version 2.20.1",
                                    "jq": "jq-1.6",
                                    "nodejs": "v12.18.3",
                                    "npm": "6.14.6",
                                    "rg": "ripgrep 0.10.0\n-SIMD -AVX (compiled)\n+SIMD +AVX (runtime)",
                                },
                                "working_dir": "/home/app",
                            }
                        ],
                    },
                }
            ]
        ],
        [
            (
                m.Advisory(
                    npm_advisory_id=1179,
                    severity="low",
                    url="https://npmjs.com/advisories/1179",
                ),
                {"0.0.8", "1.2.0"},
            ),
            (
                m.Advisory(
                    npm_advisory_id=1426,
                    severity="moderate",
                    url="https://npmjs.com/advisories/1426",
                ),
                {"1.7.0"},
            ),
            (
                m.Advisory(
                    npm_advisory_id=1548,
                    severity="high",
                    url="https://npmjs.com/advisories/1548",
                ),
                {"1.7.0"},
            ),
        ],
    ),
}


@pytest.mark.parametrize(
    "json_results, expected_models",
    deserialize_pubsub_test_cases.values(),
    ids=deserialize_pubsub_test_cases.keys(),
)
@pytest.mark.unit
def test_deserializing_pubsub_json_results(
    json_results: List[m.JSONResult], expected_models, app
):
    def package_equal(l, r):
        assert l.name == r.name
        assert l.version == r.version

    with app.app_context():
        for deserialized, expected in itertools.zip_longest(
            m.deserialize_scan_job_results(json_results), expected_models
        ):
            print(type(deserialized), type(expected))
            if isinstance(expected, m.PackageVersion):
                package_equal(deserialized, expected)
            elif isinstance(expected, tuple) and isinstance(
                expected[0], m.PackageGraph
            ):
                assert len(expected) == 3
                assert isinstance(expected[0], m.PackageGraph)
                assert isinstance(expected[1], m.PackageVersion)
                package_equal(deserialized[1], expected[1])

                assert isinstance(expected[2], list)
                for deserialized_link, expected_link in itertools.zip_longest(
                    deserialized[2], expected[2]
                ):
                    package_equal(deserialized_link[0], expected_link[0])
                    package_equal(deserialized_link[1], expected_link[1])
            elif isinstance(expected, tuple) and isinstance(expected[0], m.Advisory):
                assert len(expected) == 2
                # TODO: check more fields
                assert deserialized[0].severity == expected[0].severity
                assert deserialized[0].npm_advisory_id == expected[0].npm_advisory_id
                assert deserialized[0].url == expected[0].url
                assert deserialized[1] == expected[1]
            else:
                assert deserialized == expected
