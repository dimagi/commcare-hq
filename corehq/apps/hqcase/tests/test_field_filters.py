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


class TestExtractFieldsParams(SimpleTestCase):

    def test_no_params_returns_identity(self):
        params = QueryDict("")
        fn = get_fields_filter_fn(params)
        data = {"case_id": "abc", "case_type": "foo"}
        self.assertEqual(fn(data), data)

    def test_fields_basic(self):
        params = QueryDict("fields=case_id,case_type")
        fn = get_fields_filter_fn(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {"case_id": "abc123", "case_type": "pregnant_mother"})

    def test_exclude_basic(self):
        params = QueryDict("exclude=case_name")
        fn = get_fields_filter_fn(params)
        result = fn(SAMPLE_CASE)
        self.assertNotIn("case_name", result)
        self.assertIn("case_id", result)

    def test_both_raises_error(self):
        params = QueryDict("fields=case_id&exclude=case_name")
        with self.assertRaises(UserError):
            get_fields_filter_fn(params)

    def test_dot_param_fields(self):
        params = QueryDict("fields=case_id&fields.properties=edd,age")
        fn = get_fields_filter_fn(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {
            "case_id": "abc123",
            "properties": {"edd": "2013-12-09", "age": "22"},
        })

    def test_dot_param_without_base(self):
        params = QueryDict("fields.properties=edd")
        fn = get_fields_filter_fn(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {"properties": {"edd": "2013-12-09"}})

    def test_repeated_params(self):
        params = QueryDict("fields=case_id&fields=case_type")
        fn = get_fields_filter_fn(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {"case_id": "abc123", "case_type": "pregnant_mother"})

    def test_empty_fields_returns_empty(self):
        params = QueryDict("fields=")
        fn = get_fields_filter_fn(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {})

    def test_empty_exclude_returns_all(self):
        params = QueryDict("exclude=")
        fn = get_fields_filter_fn(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, SAMPLE_CASE)

    def test_dot_param_exclude(self):
        params = QueryDict("exclude=case_name&exclude.properties=husband_name")
        fn = get_fields_filter_fn(params)
        result = fn(SAMPLE_CASE)
        self.assertNotIn("case_name", result)
        self.assertNotIn("husband_name", result["properties"])
        self.assertIn("edd", result["properties"])

    def test_deep_dot_param(self):
        params = QueryDict("fields.a.b=c")
        data = {"a": {"b": {"c": "deep", "d": "other"}}, "x": "y"}
        fn = get_fields_filter_fn(params)
        result = fn(data)
        self.assertEqual(result, {"a": {"b": {"c": "deep"}}})


class TestFieldFilterPipeline(SimpleTestCase):
    """Integration-style tests: extract params then apply to case dicts."""

    CASE = {
        "case_id": "abc123",
        "case_type": "person",
        "case_name": "Test",
        "properties": {"edd": "2013-12-09", "age": "22", "secret": "hidden"},
        "indices": {"parent": {"case_id": "def456", "case_type": "household"}},
    }

    def test_fields_on_case_list_envelope(self):
        """Envelope fields are not filtered - only case dicts are."""
        params = QueryDict("fields=case_id")
        filter_fn = get_fields_filter_fn(params)
        envelope = {
            "matching_records": 5,
            "cases": [self.CASE],
            "next": {"cursor": "abc"},
        }
        # Apply filter to each case (as views.py does), not the envelope
        filtered_cases = [filter_fn(c) for c in envelope["cases"]]
        self.assertEqual(filtered_cases, [{"case_id": "abc123"}])
        # Envelope keys untouched
        self.assertIn("matching_records", envelope)
        self.assertIn("next", envelope)

    def test_bulk_error_stubs_not_filtered(self):
        """Error stubs should pass through unfiltered."""
        params = QueryDict("fields=case_id")
        filter_fn = get_fields_filter_fn(params)
        cases = [
            self.CASE,
            {"case_id": "missing1", "error": "not found"},
        ]
        filtered = [
            filter_fn(c) if "error" not in c else c
            for c in cases
        ]
        self.assertEqual(filtered[0], {"case_id": "abc123"})
        self.assertEqual(filtered[1], {"case_id": "missing1", "error": "not found"})

    def test_fields_on_update_response(self):
        """Update response: form_id is envelope, case is filtered."""
        params = QueryDict("fields=case_id,case_type")
        filter_fn = get_fields_filter_fn(params)
        response = {
            "form_id": "form-xyz",
            "case": filter_fn(self.CASE),
        }
        self.assertEqual(response["form_id"], "form-xyz")
        self.assertEqual(response["case"], {"case_id": "abc123", "case_type": "person"})

    def test_exclude_nested_fields(self):
        params = QueryDict("exclude.properties=secret")
        filter_fn = get_fields_filter_fn(params)
        result = filter_fn(self.CASE)
        self.assertNotIn("secret", result["properties"])
        self.assertIn("edd", result["properties"])
        # Top-level fields unchanged
        self.assertIn("case_id", result)
        self.assertIn("indices", result)
