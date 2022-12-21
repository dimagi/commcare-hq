from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test, test_adapter

from ..utils import fetch_elastic_mapping, sorted_mapping


@es_test
class TestMappingsUtilsNoIndex(SimpleTestCase):

    def test_sorted_mapping(self):
        expected_order = ["alpha", "items", "zulu", "properties"]
        unsorted = {key: None for key in expected_order[::-1]}
        mapping = unsorted.copy()
        mapping["items"] = [unsorted.copy()]
        mapping["properties"] = unsorted.copy()
        mapping = sorted_mapping(mapping)
        self.assertEqual(expected_order, list(mapping))
        self.assertEqual(expected_order, list(mapping["items"][0]))
        self.assertEqual(expected_order, list(mapping["properties"]))


@es_test(requires=[test_adapter])
class TestMappingsUtilsWithIndex(SimpleTestCase):

    def test_fetch_elastic_mapping(self):
        from_elastic = fetch_elastic_mapping(
            test_adapter.index_name,
            test_adapter.type,
        )
        self.assertEqual(test_adapter.mapping, from_elastic)
