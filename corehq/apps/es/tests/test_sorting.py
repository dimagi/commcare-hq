from django.test.testcases import SimpleTestCase

from corehq.apps.es import CaseSearchES


class TestESSort(SimpleTestCase):
    def test_regular_sort(self):
        field_name = "foo"
        expected = [{field_name: {'order': 'asc'}}]
        self.assertEqual(expected, CaseSearchES().sort(field_name).raw_query['sort'])

    def test_nested_sort(self):
        """https://www.elastic.co/guide/en/elasticsearch/reference/1.7/search-request-sort.html#_sorting_within_nested_objects
        """
        path = "case_properties"
        field_name = 'value'

        key = "dob"
        sort_filter = {
            "term": {
                "case_properties.key.exact": key
            }
        }

        expected = [{
            "case_properties.value": {
                "missing": None,
                "order": "asc",
                "nested_path": path,
                "nested_filter": sort_filter
            }
        }]
        self.assertEqual(
            expected,
            CaseSearchES().nested_sort(path, field_name, sort_filter).raw_query['sort']
        )
