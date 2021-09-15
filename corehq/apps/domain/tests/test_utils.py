import json
from unittest.mock import MagicMock

from contextlib import contextmanager

from django.test import SimpleTestCase, TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import guess_domain_language, get_serializable_wire_invoice_item_from_request
from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def delete_all_domains():
    domains = list(Domain.get_all())
    Domain.bulk_delete(domains)


class UtilsTests(TestCase):
    domain_name = 'test_domain'

    def setUp(self):
        domain = Domain(name=self.domain_name)
        domain.save()

    def tearDown(self):
        Domain.get_by_name(self.domain_name).delete()

    def test_guess_domain_language(self):
        for i, lang in enumerate(['en', 'fra', 'fra']):
            app = Application.new_app(domain=self.domain_name, name='app{}'.format(i + 1), lang=lang)
            app.save()
        lang = guess_domain_language(self.domain_name)
        self.assertEqual('fra', lang)

    def test_guess_domain_language_no_apps(self):
        lang = guess_domain_language(self.domain_name)
        self.assertEqual('en', lang)


class TestGetSerializableWireInvoiceItem(SimpleTestCase):

    def setUp(self):
        self.mock_request = MagicMock()

    def test_empty_list_is_returned_if_general_credit_is_zero(self):
        self.mock_request.POST.get.return_value = 0
        items = get_serializable_wire_invoice_item_from_request(self.mock_request)
        self.assertFalse(items)

    def test_empty_list_is_returned_if_general_credit_is_less_than_zero(self):
        self.mock_request.POST.get.return_value = -1
        items = get_serializable_wire_invoice_item_from_request(self.mock_request)
        self.assertFalse(items)

    def test_item_is_returned_if_general_credit_is_greater_than_zero(self):
        self.mock_request.POST.get.return_value = 1
        items = get_serializable_wire_invoice_item_from_request(self.mock_request)
        self.assertTrue(items)

    def test_return_value_is_json_serializable(self):
        self.mock_request.POST.get.return_value = 1.5
        items = get_serializable_wire_invoice_item_from_request(self.mock_request)
        # exception would be raised here if there is an issue
        serialized_items = json.dumps(items)
        self.assertTrue(serialized_items)

@contextmanager
def test_domain(name="domain", skip_full_delete=False):
    """Context manager for use in tests"""
    from corehq.apps.domain.shortcuts import create_domain
    domain = create_domain(name)
    try:
        yield domain
    finally:
        if skip_full_delete:
            Domain.get_db().delete_doc(domain.get_id)
        else:
            domain.delete()
