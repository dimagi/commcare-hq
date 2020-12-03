from datetime import date, timedelta

from django.test import TestCase
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.models import Invoice


# 8 tests in 1.136s
class Invoice_GetDomainInvoicesBetweenDatesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = generator.arbitrary_domain()
        cls.billing_account = generator.billing_account('test_user', 'test_user@email.com')
        cls.subscription = generator.generate_domain_subscription(cls.billing_account,
            cls.domain_obj, date(1000, 1, 1), date(3000, 1, 1))

    def setUp(self):
        self.start = date(2020, 1, 15)
        self.end = date(2020, 3, 20)

    def create_invoice(self, start, end):
        return Invoice.objects.create(subscription=self.subscription,
            date_start=start, date_end=end)

    def get_invoices(self):
        return list(Invoice.get_domain_invoices_between_dates(
            self.domain_obj, self.start, self.end))

    def test_handles_no_results(self):
        results = self.get_invoices()

        self.assertEqual(len(results), 0)

    def test_includes_invoice_during_period_inclusive(self):
        invoice = self.create_invoice(self.start, self.end)

        results = self.get_invoices()

        self.assertEqual(results, [invoice])

    def test_includes_invoice_containing_period(self):
        invoice = self.create_invoice(
            start=self.start - timedelta(days=1),
            end=self.end + timedelta(days=1))

        results = self.get_invoices()

        self.assertEqual(results, [invoice])

    def test_includes_invoice_started_before_and_ending_during_period(self):
        invoice = self.create_invoice(
            start=self.start - timedelta(days=1),
            end=self.end - timedelta(days=1))

        results = self.get_invoices()
        self.assertEqual(results, [invoice])

    def test_includes_invoice_started_during_and_ending_after_period(self):
        invoice = self.create_invoice(
            start=self.start + timedelta(days=1),
            end=self.end + timedelta(days=1))

        results = self.get_invoices()
        self.assertEqual(results, [invoice])

    def test_excludes_invoice_before_period(self):
        self.create_invoice(
            start=self.start - timedelta(days=2),
            end=self.start - timedelta(days=1))

        results = self.get_invoices()
        self.assertEqual(len(results), 0)

    def test_excludes_invoice_after_period(self):
        self.create_invoice(
            start=self.end + timedelta(days=1),
            end=self.end + timedelta(days=2))

        results = self.get_invoices()
        self.assertEqual(len(results), 0)

    def test_includes_all_during_period(self):
        invoice1 = self.create_invoice(self.start, self.end)
        invoice2 = self.create_invoice(self.start, self.end)

        results = set(self.get_invoices())
        self.assertSetEqual(results, {invoice1, invoice2})
