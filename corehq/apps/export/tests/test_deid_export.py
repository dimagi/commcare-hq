from types import SimpleNamespace

from django.test import TestCase

from corehq.apps.export.models import DeIdHash


class TestDeIdHash(TestCase):
    def test_deid_output_format(self):
        deid = DeIdHash.get_deid('somedatavalue', {'domain': 'test-domain'})
        self.assertRegex(deid, '[A-Z0-9]{10}')

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
        deid = DeIdHash.get_deid(None, {'domain': 'test-domain'})
        self.assertIsNotNone(deid)

    def test_no_value_no_doc_returns_none(self):
        deid = DeIdHash.get_deid(None, {}, domain='irrelevant-domain')
        self.assertIsNone(deid)

    def test_uses_domain_from_dict_or_object(self):
        value = 'somedatavalue'
        domain = 'test-domain'
        doc_dict = {'domain': domain}
        doc_obj = SimpleNamespace(domain=domain)

        deid_with_dict = DeIdHash.get_deid(value, doc_dict)
        deid_with_obj = DeIdHash.get_deid(value, doc_obj)
        self.assertEqual(deid_with_dict, deid_with_obj)

    def test_prefers_domain_from_kwarg(self):
        value = 'somedatavalue'
        doc_dict = {'domain': 'dict-domain'}
        doc_obj = SimpleNamespace(domain='obj-domain')
        kwarg_domain = 'the-real-domain'

        deid_with_dict = DeIdHash.get_deid(value, doc_dict, domain=kwarg_domain)
        deid_with_obj = DeIdHash.get_deid(value, doc_obj, domain=kwarg_domain)
        self.assertEqual(deid_with_dict, deid_with_obj)
