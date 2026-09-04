import datetime
from decimal import Decimal
from unittest.mock import patch

from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.accounting.models import (
    WirePrepaymentBillingRecord,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.tests.wire_invoice_base import (
    WirePrepaymentTestCase,
)


class CreateWireCreditsInvoiceTest(WirePrepaymentTestCase):
    def build_factory(self, cc_emails=()):
        return DomainWireInvoiceFactory(
            self.domain_obj.name,
            date_start=datetime.date(2027, 1, 1),
            date_end=datetime.date(2028, 1, 1),
            contact_emails=['billing@example.com'],
            cc_emails=list(cc_emails),
        )

    def create(self, cc_emails=(), **kwargs):
        return self.build_factory(cc_emails).create_wire_credits_invoice(
            Decimal('12000.00'), 'a label', Decimal('1000.00'), 12, **kwargs
        )

    def get_invoice(self):
        return WirePrepaymentInvoice.objects.get(domain=self.domain_obj.name)

    def test_queues_the_task_by_default(self):
        with patch(
            'corehq.apps.accounting.tasks.create_wire_credits_invoice.delay'
        ) as delay:
            result = self.create()

        assert delay.call_count == 1
        assert result is None

    def test_returns_the_invoice_id_when_inline(self):
        invoice_id = self.create(send_async=False)

        assert invoice_id == self.get_invoice().id

    def test_due_date_is_thirty_days_after_generation(self):
        self.create(send_async=False)

        assert self.get_invoice().date_due == (
            datetime.date.today() + datetime.timedelta(days=30)
        )

    def test_emails_the_contact_and_cc_recipients(self):
        self.create(cc_emails=['ap@example.com'], send_async=False)

        record = WirePrepaymentBillingRecord.objects.get(invoice=self.get_invoice())
        assert set(record.emailed_to_list) == {
            'billing@example.com',
            'ap@example.com',
        }
        assert not record.skipped_email
