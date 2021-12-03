from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test
from ..utils import sorted_mapping


@es_test
class TestMappingsUtils(SimpleTestCase):

    def setUp(self):
        keys = ["items", "properties", "zulu", "alpha"]
        order_items = {key: None for key in keys}
        self.mapping = order_items.copy()
        self.mapping["items"] = [order_items.copy()]
        self.mapping["properties"] = order_items.copy()

    def test_sorted_mapping(self):
        key_order = ["alpha", "items", "zulu", "properties"]
        mapping = sorted_mapping(self.mapping)
        self.assertEqual(key_order, list(mapping))
        self.assertEqual(key_order, list(mapping["items"][0]))
        self.assertEqual(key_order, list(mapping["properties"]))
