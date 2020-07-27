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


@pytest.mark.parametrize(
    "json_results",
    [
        [
            m.JSONResult(**d)
            for d in [
                {"id": "3"},  # ignore invalid results
                {
                    "id": "24",
                    "inserted_at": "2020-07-23 22:12:19.07709",
                    "url": "",
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
        ]
    ],
)
# TODO: make this actually serialize things instead of saving them too
# @pytest.mark.unit
def test_deserializing_pubsub_json_results(json_results: List[m.JSONResult], app):
    with app.app_context():
        m.deserialize_scan_job_results(json_results)
