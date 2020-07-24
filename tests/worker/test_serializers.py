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
