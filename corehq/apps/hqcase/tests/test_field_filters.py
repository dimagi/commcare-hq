from django.http import QueryDict
from django.test import SimpleTestCase

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
])
def test_get_tree(querystring, expected):
    assert _get_tree(QueryDict(querystring), 'a') == expected


class TestLimitFields(SimpleTestCase):
    def test_top_level_only(self):
        tree = {"case_id": {}, "case_type": {}}
        result = _limit_fields(SAMPLE_CASE, tree)
        self.assertEqual(result, {"case_id": "abc123", "case_type": "pregnant_mother"})

    def test_nested_fields(self):
        tree = {"case_id": {}, "properties": {"edd": {}, "age": {}}}
        result = _limit_fields(SAMPLE_CASE, tree)
        self.assertEqual(result, {
            "case_id": "abc123",
            "properties": {"edd": "2013-12-09", "age": "22"},
        })

    def test_whole_nested_object(self):
        tree = {"properties": {}}
        result = _limit_fields(SAMPLE_CASE, tree)
        self.assertEqual(result, {"properties": SAMPLE_CASE["properties"]})

    def test_nonexistent_fields_ignored(self):
        tree = {"case_id": {}, "nonexistent": {}}
        result = _limit_fields(SAMPLE_CASE, tree)
        self.assertEqual(result, {"case_id": "abc123"})

    def test_empty_tree_returns_empty(self):
        result = _limit_fields(SAMPLE_CASE, {})
        self.assertEqual(result, {})

    def test_nested_path_through_scalar(self):
        tree = {"case_id": {"nested": {}}}
        result = _limit_fields(SAMPLE_CASE, tree)
        self.assertEqual(result, {})

    def test_nested_path_through_none(self):
        data = {"case_id": "abc", "value": None}
        tree = {"value": {"nested": {}}}
        result = _limit_fields(data, tree)
        self.assertEqual(result, {})

    def test_deep_nesting(self):
        data = {"a": {"b": {"c": "deep", "d": "also_deep"}}}
        tree = {"a": {"b": {"c": {}}}}
        result = _limit_fields(data, tree)
        self.assertEqual(result, {"a": {"b": {"c": "deep"}}})


class TestExcludeFields(SimpleTestCase):
    def test_top_level_exclusion(self):
        tree = {"case_name": {}}
        result = _exclude_fields(SAMPLE_CASE, tree)
        expected = {k: v for k, v in SAMPLE_CASE.items() if k != "case_name"}
        self.assertEqual(result, expected)

    def test_nested_exclusion(self):
        tree = {"properties": {"husband_name": {}}}
        result = _exclude_fields(SAMPLE_CASE, tree)
        self.assertEqual(result["properties"], {"edd": "2013-12-09", "age": "22"})
        self.assertEqual(result["case_id"], "abc123")

    def test_exclude_whole_nested_object(self):
        tree = {"properties": {}}
        result = _exclude_fields(SAMPLE_CASE, tree)
        self.assertNotIn("properties", result)
        self.assertEqual(result["case_id"], "abc123")

    def test_nonexistent_fields_ignored(self):
        tree = {"nonexistent": {}}
        result = _exclude_fields(SAMPLE_CASE, tree)
        self.assertEqual(result, SAMPLE_CASE)

    def test_empty_tree_returns_all(self):
        result = _exclude_fields(SAMPLE_CASE, {})
        self.assertEqual(result, SAMPLE_CASE)

    def test_nested_path_through_scalar(self):
        tree = {"case_id": {"nested": {}}}
        result = _exclude_fields(SAMPLE_CASE, tree)
        self.assertEqual(result, SAMPLE_CASE)

    def test_deep_nesting(self):
        data = {"a": {"b": {"c": "deep", "d": "also_deep"}}}
        tree = {"a": {"b": {"c": {}}}}
        result = _exclude_fields(data, tree)
        self.assertEqual(result, {"a": {"b": {"d": "also_deep"}}})


class TestGetFieldsFilterFn(SimpleTestCase):
    """Tests for get_fields_filter_fn behavior not covered by the unit tests above."""

    def test_no_params_returns_identity(self):
        fn = get_fields_filter_fn(QueryDict(""))
        data = {"case_id": "abc", "case_type": "foo"}
        self.assertEqual(fn(data), data)

    def test_both_raises_error(self):
        with self.assertRaises(UserError):
            get_fields_filter_fn(QueryDict("fields=case_id&exclude=case_name"))

    def test_empty_fields_returns_empty(self):
        fn = get_fields_filter_fn(QueryDict("fields="))
        self.assertEqual(fn(SAMPLE_CASE), {})

    def test_empty_exclude_returns_all(self):
        fn = get_fields_filter_fn(QueryDict("exclude="))
        self.assertEqual(fn(SAMPLE_CASE), SAMPLE_CASE)
