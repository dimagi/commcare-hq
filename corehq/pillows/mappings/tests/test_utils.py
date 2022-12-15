from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test

from ..utils import sorted_mapping


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
