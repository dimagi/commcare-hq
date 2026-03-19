from django.http import QueryDict
from django.test import SimpleTestCase

from corehq.apps.hqcase.api.core import UserError
from corehq.apps.hqcase.api.field_filters import (
    _build_field_tree,
    _exclude_fields,
    _limit_fields,
    extract_fields_params,
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


class TestBuildFieldTree(SimpleTestCase):
    def test_top_level_fields(self):
        self.assertEqual(
            _build_field_tree(["case_id", "case_type"]),
            {"case_id": {}, "case_type": {}},
        )

    def test_dotted_fields(self):
        self.assertEqual(
            _build_field_tree(["properties.edd", "properties.age"]),
            {"properties": {"edd": {}, "age": {}}},
        )

    def test_mixed_top_and_dotted(self):
        self.assertEqual(
            _build_field_tree(["case_id", "properties.edd"]),
            {"case_id": {}, "properties": {"edd": {}}},
        )

    def test_deep_nesting(self):
        self.assertEqual(
            _build_field_tree(["a.b.c.d"]),
            {"a": {"b": {"c": {"d": {}}}}},
        )

    def test_whole_object_and_sub_field(self):
        self.assertEqual(
            _build_field_tree(["properties", "properties.edd"]),
            {"properties": {}},
        )

    def test_empty_list(self):
        self.assertEqual(_build_field_tree([]), {})


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
        fn = extract_fields_params(params)
        data = {"case_id": "abc", "case_type": "foo"}
        self.assertEqual(fn(data), data)

    def test_fields_basic(self):
        params = QueryDict("fields=case_id,case_type")
        fn = extract_fields_params(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {"case_id": "abc123", "case_type": "pregnant_mother"})

    def test_exclude_basic(self):
        params = QueryDict("exclude=case_name")
        fn = extract_fields_params(params)
        result = fn(SAMPLE_CASE)
        self.assertNotIn("case_name", result)
        self.assertIn("case_id", result)

    def test_both_raises_error(self):
        params = QueryDict("fields=case_id&exclude=case_name")
        with self.assertRaises(UserError):
            extract_fields_params(params)

    def test_dot_param_fields(self):
        params = QueryDict("fields=case_id&fields.properties=edd,age")
        fn = extract_fields_params(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {
            "case_id": "abc123",
            "properties": {"edd": "2013-12-09", "age": "22"},
        })

    def test_dot_param_without_base(self):
        params = QueryDict("fields.properties=edd")
        fn = extract_fields_params(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {"properties": {"edd": "2013-12-09"}})

    def test_repeated_params(self):
        params = QueryDict("fields=case_id&fields=case_type")
        fn = extract_fields_params(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {"case_id": "abc123", "case_type": "pregnant_mother"})

    def test_empty_fields_returns_empty(self):
        params = QueryDict("fields=")
        fn = extract_fields_params(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, {})

    def test_empty_exclude_returns_all(self):
        params = QueryDict("exclude=")
        fn = extract_fields_params(params)
        result = fn(SAMPLE_CASE)
        self.assertEqual(result, SAMPLE_CASE)

    def test_dot_param_exclude(self):
        params = QueryDict("exclude=case_name&exclude.properties=husband_name")
        fn = extract_fields_params(params)
        result = fn(SAMPLE_CASE)
        self.assertNotIn("case_name", result)
        self.assertNotIn("husband_name", result["properties"])
        self.assertIn("edd", result["properties"])

    def test_deep_dot_param(self):
        params = QueryDict("fields.a.b=c")
        data = {"a": {"b": {"c": "deep", "d": "other"}}, "x": "y"}
        fn = extract_fields_params(params)
        result = fn(data)
        self.assertEqual(result, {"a": {"b": {"c": "deep"}}})
