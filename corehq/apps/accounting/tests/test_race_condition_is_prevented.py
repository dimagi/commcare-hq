from corehq.apps.accounting.invoicing import DomainInvoiceFactory
from corehq.apps.accounting.models import DomainUserHistory
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.accounting import utils
import random
from corehq.util.dates import get_previous_month_date_range


class UniqueConstraintTest(BaseInvoiceTestCase):

    def test_unique_constraint_prevents_duplicate_invoice(self):
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        invoice_start, invoice_end = get_previous_month_date_range(invoice_date)

        DomainUserHistory.objects.create(
            domain=self.domain.name,
            record_date=invoice_end,
            num_users=4
        )

        invoice_factory = DomainInvoiceFactory(invoice_start, invoice_end, self.domain)
        invoice_factory.create_invoices()
        with self.assertLogs(level='ERROR') as log_cm:
            invoice_factory.create_invoices()
            self.assertIn("[BILLING] Invoice already existed", log_cm.output[0])
