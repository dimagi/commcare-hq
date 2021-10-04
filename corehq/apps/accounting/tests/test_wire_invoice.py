from decimal import Decimal

from django.core import mail

from corehq.apps.accounting import tasks, utils
from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.accounting.models import Invoice
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase


class TestWireInvoice(BaseInvoiceTestCase):

    def setUp(self):
        super(TestWireInvoice, self).setUp()
        invoice_date = utils.months_from_date(self.subscription.date_start, 2)
        tasks.calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        invoice_date = utils.months_from_date(self.subscription.date_start, 3)
        tasks.calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.invoices = Invoice.objects.all()

    def test_factory(self):
        factory = DomainWireInvoiceFactory(
            self.domain.name,
            contact_emails=[self.dimagi_user],
        )
        balance = Decimal(100)

        mail.outbox = []
        wi = factory.create_wire_invoice(balance)

        self.assertEqual(wi.balance, balance)
        self.assertEqual(wi.domain, self.domain.name)
        self.assertEqual(len(mail.outbox), 1)


class TestCustomerAccountWireInvoice(BaseInvoiceTestCase):

    def setUp(self):
        super(TestCustomerAccountWireInvoice, self).setUp()
        self.account.is_customer_billing_account = True
        self.account.save()

        invoice_date = utils.months_from_date(self.subscription.date_start, 2)
        tasks.calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        invoice_date = utils.months_from_date(self.subscription.date_start, 3)
        tasks.calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

    def test_factory(self):
        factory = DomainWireInvoiceFactory(
            self.domain.name,
            contact_emails=[self.dimagi_user],
            account=self.account
        )
        balance = Decimal(100)

        mail.outbox = []
        wi = factory.create_wire_invoice(balance)

        self.assertEqual(wi.balance, balance)
        self.assertEqual(wi.domain, self.domain.name)
        self.assertEqual(len(mail.outbox), 1)
