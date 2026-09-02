import datetime
from decimal import Decimal
from unittest.mock import patch

from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.accounting.models import (
    INACTIVE_SUBSCRIPTION_REASON,
    ScheduledPrepaymentInvoice,
    ScheduledPrepaymentInvoiceStatus,
    SoftwarePlanEdition,
    Subscription,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.tasks import (
    cancel_scheduled_invoices_for_inactive_subscriptions,
    generate_due_scheduled_invoices,
    process_scheduled_prepayment_invoices_for_domain,
)
from corehq.apps.accounting.tests import generator
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

    def test_lists_a_domain_once_however_many_are_pending(self):
        self.schedule(send_date=datetime.date.today())
        self.schedule(send_date=in_days(-1))

        assert ScheduledPrepaymentInvoice.objects.pending_domains() == [
            self.domain_obj.name
        ]

    def test_the_per_domain_task_sends_that_domain_s_requests(self):
        self.schedule(send_date=datetime.date.today())
        self.schedule(send_date=in_days(-1))

        process_scheduled_prepayment_invoices_for_domain(self.domain_obj.name)

        assert self.get_invoices().count() == 2
        assert not ScheduledPrepaymentInvoice.objects.filter(
            domain=self.domain_obj.name,
            status=ScheduledPrepaymentInvoiceStatus.PENDING,
        ).exists()

    def deactivate_subscription(self):
        # queryset update rather than mutating self.subscription: the object is
        # built in setUpClass, so an in-memory change would outlive the
        # transaction and leak into later tests
        Subscription.visible_objects.filter(id=self.subscription.id).update(is_active=False)

    def pause_subscription(self):
        paused = generator.subscribable_plan_version(SoftwarePlanEdition.PAUSED)
        Subscription.visible_objects.filter(id=self.subscription.id).update(
            plan_version=paused
        )

    def test_cancels_when_the_subscription_is_paused(self):
        scheduled = self.schedule(send_date=in_days(30))
        self.pause_subscription()

        cancel_scheduled_invoices_for_inactive_subscriptions()

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED

    def test_cancels_when_the_subscription_is_no_longer_active(self):
        scheduled = self.schedule(send_date=in_days(30))
        self.deactivate_subscription()

        cancel_scheduled_invoices_for_inactive_subscriptions()

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED

    def test_records_why_the_system_cancelled_it(self):
        scheduled = self.schedule(send_date=in_days(30))
        self.deactivate_subscription()

        cancel_scheduled_invoices_for_inactive_subscriptions()

        scheduled.refresh_from_db()
        assert scheduled.cancelled_reason == INACTIVE_SUBSCRIPTION_REASON
        # blank cancelled_by is what marks this as the system, not an operator
        assert scheduled.cancelled_by == ''

    def test_leaves_an_active_subscription_alone(self):
        scheduled = self.schedule(send_date=in_days(30))

        cancel_scheduled_invoices_for_inactive_subscriptions()

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.PENDING

    def test_a_paused_subscription_stops_a_send_due_today(self):
        scheduled = self.schedule(send_date=datetime.date.today())
        self.deactivate_subscription()

        process_scheduled_prepayment_invoices_for_domain(self.domain_obj.name)

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED
        assert not self.get_invoices().exists()

    def test_fans_out_to_domains_whose_requests_are_not_due_yet(self):
        self.schedule(send_date=in_days(30))

        pending = ScheduledPrepaymentInvoice.objects.pending_domains()

        assert pending == [self.domain_obj.name]
