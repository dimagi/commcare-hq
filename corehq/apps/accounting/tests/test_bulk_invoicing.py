import random

from django.core import mail

from corehq.apps.accounting import generator, tasks, utils
from corehq.apps.accounting.invoicing import DomainBulkInvoiceFactory
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.accounting.models import BulkInvoice, Invoice, CreditLine, BillingRecord
from corehq.apps.accounting.utils import get_dimagi_from_email


class BulkInvoiceTestCase(BaseInvoiceTestCase):

    def setUp(self):
        super(BulkInvoiceTestCase, self).setUp()
        invoice_date = utils.months_from_date(self.subscription.date_start, 2)
        tasks.generate_invoices(invoice_date)

        invoice_date = utils.months_from_date(self.subscription.date_start, 3)
        tasks.generate_invoices(invoice_date)

        self.bulk_invoice = BulkInvoice.objects.create()
        self.bulk_invoice.invoice_set = Invoice.objects.all()

        self.invoices = Invoice.objects.all()

    def tearDown(self):
        super(BulkInvoiceTestCase, self).tearDown()
        self.invoices.delete()
        self.bulk_invoice.delete()

    def test_balance(self):

        self.assertEqual(self.bulk_invoice.balance, self.invoices[0].balance + self.invoices[1].balance)

        # Add some credit
        before_balance = sum(map(lambda i: i.balance, Invoice.objects.all()))
        credit = 100
        CreditLine.add_credit(credit, subscription=self.subscription)
        for i in Invoice.objects.all():
            i.calculate_credit_adjustments()
            i.update_balance()
            i.save()

        self.bulk_invoice = BulkInvoice.objects.get(id=self.bulk_invoice.id)
        self.assertEqual(self.bulk_invoice.balance, before_balance - credit)

    def test_dates(self):
        start_dates = sorted(map(lambda i: i.date_start, self.invoices))
        end_dates = sorted(map(lambda i: i.date_end, self.invoices))
        due_dates = sorted(map(lambda i: i.date_due, self.invoices))

        self.assertEqual(self.bulk_invoice.date_start, start_dates[0])
        self.assertEqual(self.bulk_invoice.date_end, end_dates[1])
        self.assertEqual(self.bulk_invoice.date_due, due_dates[1])

    def test_project_name(self):
        project_name = self.bulk_invoice.get_project_name()
        self.assertEqual(project_name, self.invoices[0].subscription.subscriber.domain)

    def test_billing_record(self):
        mail.outbox = []
        br = BillingRecord.generate_record(self.bulk_invoice)
        br.send_email()

        self.assertEqual(len(mail.outbox),
            sum([len(i.email_recipients) for i in self.invoices]))

        msg = mail.outbox[0]
        self.assertEqual(len(msg.attachments), 1)
        self.assertEqual(msg.from_email, get_dimagi_from_email())

    def test_bulk_invoice_factory(self):
        mail.outbox = []
        self.bulk_invoice.delete()
        bi_factory = DomainBulkInvoiceFactory(self.bulk_invoice.get_project_name())
        bi = bi_factory.create_bulk_invoice()

        self.assertEqual(len(bi.invoice_set.all()), 2)
        self.assertEqual(len(mail.outbox),
            sum([len(i.email_recipients) for i in self.invoices]))

        bi_factory = DomainBulkInvoiceFactory(
            self.bulk_invoice.get_project_name(),
            contact_emails=emails
        )

        # Once invoices get assigned to bulk invoice, don't overwrite
        with self.assertRaises(BulkInvoiceNoInvoicesError):
            bi = bi_factory.create_bulk_invoice(self.invoices)
