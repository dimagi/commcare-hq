from decimal import Decimal
from django.core import mail

from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.accounting import utils, tasks
from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.accounting.models import Invoice


class TestWireInvoice(BaseInvoiceTestCase):

    def setUp(self):
        super(TestWireInvoice, self).setUp()
        invoice_date = utils.months_from_date(self.subscription.date_start, 2)
        tasks.generate_invoices(invoice_date)

        invoice_date = utils.months_from_date(self.subscription.date_start, 3)
        tasks.generate_invoices(invoice_date)

        self.invoices = Invoice.objects.all()
        self.domain_name = self.invoices[0].get_domain()

    def tearDown(self):
        super(TestWireInvoice, self).tearDown()

    def test_factory(self):
        factory = DomainWireInvoiceFactory(
            self.domain_name,
            contact_emails=[self.dimagi_user.username],
        )
        balance = Decimal(100)

        mail.outbox = []
        wi = factory.create_wire_invoice(balance)

        self.assertEqual(wi.balance, balance)
        self.assertEqual(wi.domain, self.domain.name)
        self.assertEqual(len(mail.outbox), 1)
