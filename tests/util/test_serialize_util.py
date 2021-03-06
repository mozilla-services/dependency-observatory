# -*- coding: utf-8 -*-

import pytest

import depobs.util.serialize_util as m


default_get_in_obj = {"a": 1, "b": {"foo": [-1, {}]}}


@pytest.mark.parametrize(
    "value,path,default,expected",
    [
        (default_get_in_obj, [], None, {"a": 1, "b": {"foo": [-1, {}]}}),
        (default_get_in_obj, [-7], "not found", "not found"),
        (default_get_in_obj, ["a"], None, 1),
        (default_get_in_obj, ["b", "foo", 1], None, {}),
        (default_get_in_obj, ["b", "foo", 1], None, {}),
        ("", [""], None, None),
        (set(), [-1], None, None),
    ],
)
@pytest.mark.unit
def test_get_in(value, path, default, expected):
    assert m.get_in(value, path, default) == expected


@pytest.mark.parametrize(
    "value,path,default,expected_error", [({}, [set()], None, NotImplementedError)]
)
@pytest.mark.unit
def test_get_in_errors(value, path, default, expected_error):
    with pytest.raises(expected_error):
        m.get_in(value, path, default)
