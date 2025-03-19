import random
from corehq.apps.accounting import tasks

from corehq.apps.accounting.invoicing import DomainInvoiceFactory
from corehq.apps.accounting.models import DomainUserHistory, Invoice, CustomerInvoice
from corehq.apps.accounting.tasks import calculate_users_in_all_domains
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.accounting.tests.test_customer_invoicing import BaseCustomerInvoiceCase
from corehq.apps.accounting import utils
from corehq.util.dates import get_previous_month_date_range


class UniqueConstraintInvoiceTest(BaseInvoiceTestCase):

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
            self.assertIn("[BILLING] Invoice already existed", "\n".join(log_cm.output))

        invoices = Invoice.objects.filter(
            date_start=invoice_factory.date_start,
            date_end=invoice_factory.date_end,
        )
        self.assertEqual(invoices.count(), 1)


class UniqueConstraintCustomerInvoiceTest(BaseCustomerInvoiceCase):
    def test_unique_constraint_prevents_duplicate_customer_invoice(self):
        invoice_date = utils.months_from_date(self.main_subscription.date_start,
                                              random.randint(3, self.main_subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        with self.assertLogs(level='ERROR') as log_cm:
            tasks.generate_invoices_based_on_date(invoice_date)
            self.assertIn("[BILLING] Invoice already existed", "\n".join(log_cm.output))

        self.assertEqual(CustomerInvoice.objects.count(), 1)
