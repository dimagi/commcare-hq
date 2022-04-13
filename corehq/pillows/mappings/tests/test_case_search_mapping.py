from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test

from ..case_search_mapping import CASE_SEARCH_MAPPING


@es_test
class TestCaseSearchMapping(SimpleTestCase):

    def test_case_search_property_domain_not_indexed(self):
        self.assertEqual(CASE_SEARCH_MAPPING["properties"]["domain"]["index"], "no")
