from django.http import QueryDict

import pytest

from corehq.apps.hqcase.api.core import UserError
from corehq.apps.hqcase.api.field_filters import (
    _exclude_fields,
    _get_tree,
    _limit_fields,
    get_fields_filter_fn,
)

SAMPLE_CASE = {
    "case_id": "abc123",
    "case_type": "pregnant_mother",
    "case_name": "Hermes Adama",
    "properties": {
        "edd": "2013-12-09",
        "age": "22",
        "husband_name": "",
    },
    "indices": {},
}


def test_get_tree_realistic():
    qs = 'fields=case_id&fields=case_name&fields.properties=dob,edd'
    assert _get_tree(QueryDict(qs), 'fields') == {
        'case_id': {},
        'case_name': {},
        'properties': {'dob': {}, 'edd': {}},
    }


@pytest.mark.parametrize("querystring, expected", [
    ("a=A&a=B&x=Y", {'A': {}, 'B': {}}),
    ("a.A=B&a.C=D", {'A': {'B': {}},
                     'C': {'D': {}}}),
    ("a.A=B&a.A=C", {'A': {'B': {}, 'C': {}}}),
    ("a=A.B&a=A.C", {'A': {'B': {}, 'C': {}}}),
    ("a.A=B&a=A.C", {'A': {'B': {}, 'C': {}}}),
    ("a.A=B,C", {'A': {'B': {}, 'C': {}}}),
    ("a.A=B,C&a.A=D", {'A': {'B': {}, 'C': {}, 'D': {}}}),

    ("", {}),
    ("somethingelse=yes", {}),

    # Whitespace is not stripped: "a=x, y" produces a key " y", not "y"
    ("a=x, y", {'x': {}, ' y': {}}),
    # Trailing comma produces an empty-string key
    ("a=x,", {'x': {}, '': {}}),
    # Empty value produces an empty-string key
    ("a=", {'': {}}),
    # Empty dot-param value produces an empty-string key in the subtree
    ("a.b=", {'b': {'': {}}}),
])
def test_get_tree(querystring, expected):
    assert _get_tree(QueryDict(querystring), 'a') == expected


@pytest.mark.parametrize("tree, expected", [
    ({"case_id": {}, "case_type": {}},
     {"case_id": "abc123", "case_type": "pregnant_mother"}),
    ({"case_id": {}, "properties": {"edd": {}, "age": {}}},
     {"case_id": "abc123", "properties": {"edd": "2013-12-09", "age": "22"}}),
    ({"properties": {}},
     {"properties": SAMPLE_CASE["properties"]}),
    ({"case_id": {}, "nonexistent": {}},
     {"case_id": "abc123"}),
    ({}, {}),
    # nested path through scalar — skipped
    ({"case_id": {"nested": {}}}, {}),
])
def test_limit_fields(tree, expected):
    assert _limit_fields(SAMPLE_CASE, tree) == expected


def test_limit_fields_nested_path_through_none():
    data = {"case_id": "abc", "value": None}
    assert _limit_fields(data, {"value": {"nested": {}}}) == {}


def test_limit_fields_deep_nesting():
    data = {"a": {"b": {"c": "deep", "d": "also_deep"}}}
    assert _limit_fields(data, {"a": {"b": {"c": {}}}}) == {"a": {"b": {"c": "deep"}}}


@pytest.mark.parametrize("tree, expected", [
    ({"case_name": {}},
     {k: v for k, v in SAMPLE_CASE.items() if k != "case_name"}),
    ({"properties": {"husband_name": {}}},
     {**SAMPLE_CASE, "properties": {"edd": "2013-12-09", "age": "22"}}),
    ({"properties": {}},
     {k: v for k, v in SAMPLE_CASE.items() if k != "properties"}),
    ({"nonexistent": {}}, SAMPLE_CASE),
    ({}, SAMPLE_CASE),
    # nested path through scalar — data unchanged
    ({"case_id": {"nested": {}}}, SAMPLE_CASE),
])
def test_exclude_fields(tree, expected):
    assert _exclude_fields(SAMPLE_CASE, tree) == expected


def test_exclude_fields_deep_nesting():
    data = {"a": {"b": {"c": "deep", "d": "also_deep"}}}
    assert _exclude_fields(data, {"a": {"b": {"c": {}}}}) == {"a": {"b": {"d": "also_deep"}}}


def test_filter_fn_no_params_returns_identity():
    fn = get_fields_filter_fn(QueryDict(""))
    data = {"case_id": "abc", "case_type": "foo"}
    assert fn(data) == data


def test_filter_fn_both_raises_error():
    with pytest.raises(UserError):
        get_fields_filter_fn(QueryDict("fields=case_id&exclude=case_name"))


def test_filter_fn_empty_fields_returns_empty():
    fn = get_fields_filter_fn(QueryDict("fields="))
    assert fn(SAMPLE_CASE) == {}


def test_filter_fn_empty_exclude_returns_all():
    fn = get_fields_filter_fn(QueryDict("exclude="))
    assert fn(SAMPLE_CASE) == SAMPLE_CASE
