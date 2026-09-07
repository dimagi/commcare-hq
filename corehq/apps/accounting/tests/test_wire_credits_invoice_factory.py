import datetime
from decimal import Decimal
from unittest.mock import patch

from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.accounting.models import WirePrepaymentInvoice
from corehq.apps.accounting.tests.wire_invoice_base import (
    WirePrepaymentTestCase,
)


class CreateWireCreditsInvoiceTest(WirePrepaymentTestCase):
    def build_factory(self):
        return DomainWireInvoiceFactory(
            self.domain_obj.name,
            date_start=datetime.date(2027, 1, 1),
            date_end=datetime.date(2028, 1, 1),
            contact_emails=['billing@example.com'],
            cc_emails=[],
        )

    def create(self, **kwargs):
        return self.build_factory().create_wire_credits_invoice(
            Decimal('12000.00'), 'a label', Decimal('1000.00'), 12, **kwargs
        )

    def test_queues_the_task_by_default(self):
        with patch(
            'corehq.apps.accounting.tasks.create_wire_credits_invoice.delay'
        ) as delay:
            result = self.create()

        assert delay.call_count == 1
        assert result is None

    def test_returns_the_invoice_id_when_inline(self):
        invoice_id = self.create(send_async=False)

        invoice = WirePrepaymentInvoice.objects.get(domain=self.domain_obj.name)
        assert invoice_id == invoice.id
