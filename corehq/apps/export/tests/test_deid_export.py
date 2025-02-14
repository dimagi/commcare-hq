from django.test import TestCase

from corehq.apps.export.models import DeIdMapping


class TestDeIdMapping(TestCase):
    def test_deid_unique_by_domain(self):
        value = 'somedatavalue'

        deid_one = DeIdMapping.get_deid(value, {'domain': 'test-domain-1'})
        deid_two = DeIdMapping.get_deid(value, {'domain': 'test-domain-2'})
        self.assertNotEqual(deid_one, deid_two)

    def test_deid_consistent_for_value_and_domain(self):
        value = 'somedatavalue'
        domain = 'test-domain'

        deid_one = DeIdMapping.get_deid(value, {'domain': domain})
        deid_two = DeIdMapping.get_deid(value, {'domain': domain})
        self.assertEqual(deid_one, deid_two)

    def test_none_is_a_deidentifiable_value(self):
        value = None

        deid = DeIdMapping.get_deid(value, {'domain': 'test-domain'})
        self.assertIsNotNone(deid)
