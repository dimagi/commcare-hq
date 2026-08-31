import datetime

from django.test import RequestFactory

from corehq.apps.accounting.interface import WireInvoiceInterface
from corehq.apps.accounting.models import WireInvoice
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest


class TestWireInvoiceInterfaceNumberFilter(BaseAccountingTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.invoice1 = WireInvoice.objects.create(
            domain='wire-interface-domain-1',
            date_start=datetime.date(2024, 1, 1),
            date_end=datetime.date(2024, 1, 31),
        )
        cls.invoice2 = WireInvoice.objects.create(
            domain='wire-interface-domain-2',
            date_start=datetime.date(2024, 2, 1),
            date_end=datetime.date(2024, 2, 29),
        )

    def test_no_filter_returns_all_invoices(self):
        interface = self._make_interface()
        self.assertEqual(
            {invoice.pk for invoice in interface._invoices},
            {self.invoice1.pk, self.invoice2.pk},
        )

    def test_filter_by_invoice_number_returns_matching_invoice(self):
        interface = self._make_interface(wire_invoice_number=str(self.invoice1.pk))
        self.assertEqual(list(interface._invoices), [self.invoice1])

    def test_filter_by_nonexistent_invoice_number_returns_empty(self):
        interface = self._make_interface(wire_invoice_number='999999999')
        self.assertEqual(list(interface._invoices), [])

    @staticmethod
    def _make_interface(wire_invoice_number=None):
        params = {}
        if wire_invoice_number is not None:
            params['wire_invoice_number'] = wire_invoice_number
        request = RequestFactory().get('/test', data=params)
        # Bypass GenericReportView.__init__, which requires a fully set up
        # request (couch_user, domain document, etc.) unrelated to the
        # queryset-filtering logic under test here.
        interface = WireInvoiceInterface.__new__(WireInvoiceInterface)
        interface.request = request
        interface.domain = None
        return interface
