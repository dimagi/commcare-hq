import datetime

from django.test import RequestFactory

from corehq.apps.accounting.async_handlers import WireInvoiceNumberAsyncHandler
from corehq.apps.accounting.models import WireInvoice
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest


class TestWireInvoiceNumberAsyncHandler(BaseAccountingTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.invoice1 = WireInvoice.objects.create(
            domain='wire-domain-1',
            date_start=datetime.date(2024, 1, 1),
            date_end=datetime.date(2024, 1, 31),
        )
        cls.invoice2 = WireInvoice.objects.create(
            domain='wire-domain-2',
            date_start=datetime.date(2024, 2, 1),
            date_end=datetime.date(2024, 2, 29),
        )

    def test_query_without_search_string_returns_all_wire_invoices(self):
        handler = self._make_handler()
        self.assertEqual(
            {invoice.pk for invoice in handler.query},
            {self.invoice1.pk, self.invoice2.pk},
        )

    def test_query_filters_by_search_string(self):
        handler = self._make_handler(search_string=str(self.invoice1.invoice_number))
        self.assertEqual(list(handler.query), [self.invoice1])

    def test_query_with_no_matching_search_string_returns_empty(self):
        handler = self._make_handler(search_string='does-not-exist')
        self.assertEqual(list(handler.query), [])

    def test_wire_invoice_number_response_returns_select2_formatted_data(self):
        handler = self._make_handler(search_string=str(self.invoice1.invoice_number))
        self.assertEqual(
            handler.wire_invoice_number_response,
            [{'id': str(self.invoice1.pk), 'text': str(self.invoice1.invoice_number)}],
        )

    @staticmethod
    def _make_handler(search_string=None):
        data = {'action': 'wire_invoice_number'}
        if search_string is not None:
            data['q'] = search_string
        request = RequestFactory().post('/test', data=data)
        return WireInvoiceNumberAsyncHandler(request)
