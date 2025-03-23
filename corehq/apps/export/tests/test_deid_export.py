from types import SimpleNamespace

from django.test import TestCase

from corehq.apps.export.models import DeIdHash


class TestDeIdHash(TestCase):
    def test_deid_unique_by_domain(self):
        value = 'somedatavalue'

        deid_one = DeIdHash.get_deid(value, {'domain': 'test-domain-1'})
        deid_two = DeIdHash.get_deid(value, {'domain': 'test-domain-2'})
        self.assertNotEqual(deid_one, deid_two)

    def test_deid_consistent_for_value_and_domain(self):
        value = 'somedatavalue'
        domain = 'test-domain'

        deid_one = DeIdHash.get_deid(value, {'domain': domain})
        deid_two = DeIdHash.get_deid(value, {'domain': domain})
        self.assertEqual(deid_one, deid_two)

    def test_none_is_a_deidentifiable_value(self):
        value = None

        deid = DeIdHash.get_deid(value, {'domain': 'test-domain'})
        self.assertIsNotNone(deid)

    def test_uses_domain_from_dict_or_object(self):
        value = 'somedatavalue'
        domain = 'test-domain'
        doc_dict = {'domain': domain}
        doc_obj = SimpleNamespace(domain=domain)

        deid_with_dict = DeIdHash.get_deid(value, doc_dict)
        deid_with_obj = DeIdHash.get_deid(value, doc_obj)
        self.assertEqual(deid_with_dict, deid_with_obj)
