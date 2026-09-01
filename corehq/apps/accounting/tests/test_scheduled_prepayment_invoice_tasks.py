import datetime
from decimal import Decimal
from unittest.mock import patch

from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.accounting.models import (
    ScheduledPrepaymentInvoice,
    ScheduledPrepaymentInvoiceStatus,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.tasks import (
    generate_due_scheduled_invoices,
    process_scheduled_prepayment_invoices_for_domain,
)
from corehq.apps.accounting.tests.wire_invoice_base import (
    WirePrepaymentTestCase,
)


def in_days(days):
    return datetime.date.today() + datetime.timedelta(days=days)


class ScheduledPrepaymentInvoiceTaskTest(WirePrepaymentTestCase):
    def schedule(self, **overrides):
        kwargs = {
            'domain': self.domain_obj.name,
            'subscription': self.subscription,
            'send_date': in_days(90),
            'amount': Decimal('12000.00'),
            'credit_label': '12 month prepayment',
            'unit_cost': Decimal('1000.00'),
            'quantity': 12,
            'contact_emails': ['billing@example.com'],
            'cc_emails': ['ap@example.com'],
            'date_start': datetime.date(2027, 4, 1),
            'date_end': datetime.date(2027, 7, 1),
            'created_by': self.username,
        }
        kwargs.update(overrides)
        return ScheduledPrepaymentInvoice.objects.create(**kwargs)

    def get_invoices(self):
        return WirePrepaymentInvoice.objects.filter(domain=self.domain_obj.name)

    def test_sends_an_invoice_due_today(self):
        scheduled = self.schedule(send_date=datetime.date.today())

        generate_due_scheduled_invoices(datetime.date.today())

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.SENT
        invoice = self.get_invoices().get()
        assert scheduled.invoice_id == invoice.id
        assert invoice.balance == Decimal('12000.0000')
        assert invoice.date_start == datetime.date(2027, 4, 1)
        assert invoice.date_end == datetime.date(2027, 7, 1)

    def test_due_date_is_thirty_days_after_the_send_date(self):
        self.schedule(send_date=datetime.date.today())

        generate_due_scheduled_invoices(datetime.date.today())

        assert self.get_invoices().get().date_due == in_days(30)

    def test_catches_up_on_an_overdue_request(self):
        self.schedule(send_date=in_days(-3))

        generate_due_scheduled_invoices(datetime.date.today())

        assert self.get_invoices().count() == 1

    def test_leaves_a_future_request_alone(self):
        scheduled = self.schedule(send_date=in_days(1))

        generate_due_scheduled_invoices(datetime.date.today())

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.PENDING
        assert not self.get_invoices().exists()

    def test_sends_only_once_when_run_twice(self):
        self.schedule(send_date=datetime.date.today())

        generate_due_scheduled_invoices(datetime.date.today())
        generate_due_scheduled_invoices(datetime.date.today())

        assert self.get_invoices().count() == 1

    def test_skips_a_cancelled_request(self):
        scheduled = self.schedule(
            send_date=datetime.date.today(),
            status=ScheduledPrepaymentInvoiceStatus.CANCELLED,
        )

        generate_due_scheduled_invoices(datetime.date.today())

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED
        assert not self.get_invoices().exists()

    def test_failure_leaves_the_request_pending(self):
        scheduled = self.schedule(send_date=datetime.date.today())

        with patch.object(
            DomainWireInvoiceFactory,
            'create_wire_credits_invoice',
            side_effect=Exception('boom'),
        ):
            generate_due_scheduled_invoices(datetime.date.today())

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.PENDING
        assert scheduled.failure_count == 1
        assert not self.get_invoices().exists()

    def test_gives_up_after_three_failures(self):
        scheduled = self.schedule(send_date=datetime.date.today())

        with patch.object(
            DomainWireInvoiceFactory,
            'create_wire_credits_invoice',
            side_effect=Exception('boom'),
        ):
            for _ in range(3):
                generate_due_scheduled_invoices(datetime.date.today())

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.FAILED
        assert scheduled.failure_count == 3

    def test_does_not_retry_a_failed_request(self):
        scheduled = self.schedule(
            send_date=datetime.date.today(),
            status=ScheduledPrepaymentInvoiceStatus.FAILED,
        )

        generate_due_scheduled_invoices(datetime.date.today())

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.FAILED
        assert not self.get_invoices().exists()
    def test_lists_only_domains_with_something_due(self):
        self.schedule(send_date=datetime.date.today())

        due = ScheduledPrepaymentInvoice.objects.due_domains(datetime.date.today())

        assert due == [self.domain_obj.name]

    def test_ignores_domains_whose_requests_are_not_due(self):
        self.schedule(send_date=in_days(1))

        assert ScheduledPrepaymentInvoice.objects.due_domains(datetime.date.today()) == []

    def test_lists_a_domain_once_however_many_are_due(self):
        self.schedule(send_date=datetime.date.today())
        self.schedule(send_date=in_days(-1))

        due = ScheduledPrepaymentInvoice.objects.due_domains(datetime.date.today())

        assert due == [self.domain_obj.name]

    def test_the_per_domain_task_sends_that_domain_s_requests(self):
        self.schedule(send_date=datetime.date.today())
        self.schedule(send_date=in_days(-1))

        process_scheduled_prepayment_invoices_for_domain(self.domain_obj.name)

        assert self.get_invoices().count() == 2
        assert not ScheduledPrepaymentInvoice.objects.filter(
            domain=self.domain_obj.name,
            status=ScheduledPrepaymentInvoiceStatus.PENDING,
        ).exists()
