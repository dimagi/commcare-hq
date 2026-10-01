import datetime
from decimal import Decimal
from unittest.mock import patch

from django.core import mail

from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.accounting.models import (
    INACTIVE_SUBSCRIPTION_REASON,
    ScheduledPrepaymentInvoice,
    ScheduledPrepaymentInvoiceStatus,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionType,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.tasks import (
    cancel_scheduled_invoices_for_inactive_subscriptions,
    generate_due_scheduled_invoices,
    notify_upcoming_scheduled_invoices,
    process_scheduled_prepayment_invoices_for_domain,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.wire_invoice_base import (
    WirePrepaymentTestCase,
)


def in_days(days):
    return datetime.date.today() + datetime.timedelta(days=days)


class ScheduledPrepaymentInvoiceTaskTest(WirePrepaymentTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_domain_obj = generator.arbitrary_domain()
        cls.addClassCleanup(cls.other_domain_obj.delete)
        cls.other_subscription = generator.generate_domain_subscription(
            cls.account,
            cls.other_domain_obj,
            date_start=in_days(-30),
            date_end=None,
            plan_version=generator.subscribable_plan_version(cls.plan_edition),
            service_type=SubscriptionType.PRODUCT,
            is_active=True,
        )

    def test_sends_an_invoice_due_today(self):
        scheduled = self.schedule(send_date=datetime.date.today())

        generate_due_scheduled_invoices(
            datetime.date.today(), self.domain_obj.name
        )

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.SENT
        invoice = self.get_invoices().get()
        assert scheduled.invoice_id == invoice.id
        assert invoice.balance == Decimal('12000.0000')
        assert invoice.date_start == datetime.date(2027, 4, 1)
        assert invoice.date_end == datetime.date(2027, 7, 1)
        assert invoice.date_due == in_days(30)

    def test_catches_up_on_an_overdue_request(self):
        self.schedule(send_date=in_days(-3))

        generate_due_scheduled_invoices(
            datetime.date.today(), self.domain_obj.name
        )

        assert self.get_invoices().count() == 1

    def test_leaves_a_future_request_alone(self):
        scheduled = self.schedule(send_date=in_days(1))

        generate_due_scheduled_invoices(
            datetime.date.today(), self.domain_obj.name
        )

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.PENDING
        assert not self.get_invoices().exists()

    def test_sends_only_once_when_run_twice(self):
        self.schedule(send_date=datetime.date.today())

        generate_due_scheduled_invoices(datetime.date.today(), self.domain_obj.name)
        generate_due_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        assert self.get_invoices().count() == 1

    def test_skips_a_cancelled_request(self):
        scheduled = self.schedule(
            send_date=datetime.date.today(),
            status=ScheduledPrepaymentInvoiceStatus.CANCELLED,
        )

        generate_due_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

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
            generate_due_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

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
                generate_due_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.FAILED
        assert scheduled.failure_count == 3

    def test_does_not_retry_a_failed_request(self):
        scheduled = self.schedule(
            send_date=datetime.date.today(),
            status=ScheduledPrepaymentInvoiceStatus.FAILED,
        )

        generate_due_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.FAILED
        assert not self.get_invoices().exists()

    def test_lists_only_domains_with_pending_requests(self):
        self.schedule(send_date=datetime.date.today())
        self.schedule_in_another_domain(
            send_date=datetime.date.today(),
            status=ScheduledPrepaymentInvoiceStatus.CANCELLED,
        )

        assert ScheduledPrepaymentInvoice.objects.pending_domains() == {
            self.domain_obj.name
        }

    def test_per_domain_task_only_sends_specified_domain(self):
        self.schedule(send_date=datetime.date.today())
        self.schedule(send_date=in_days(-1))

        process_scheduled_prepayment_invoices_for_domain(self.domain_obj.name)

        assert self.get_invoices().count() == 2
        assert not ScheduledPrepaymentInvoice.objects.filter(
            domain=self.domain_obj.name,
            status=ScheduledPrepaymentInvoiceStatus.PENDING,
        ).exists()

    def test_cancels_when_the_subscription_is_paused(self):
        scheduled = self.schedule(send_date=in_days(30))
        self.pause_subscription()

        cancel_scheduled_invoices_for_inactive_subscriptions(self.domain_obj.name)

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED

    def test_cancels_when_the_subscription_is_no_longer_active(self):
        scheduled = self.schedule(send_date=in_days(30))
        self.deactivate_subscription()

        cancel_scheduled_invoices_for_inactive_subscriptions(self.domain_obj.name)

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED
        assert scheduled.cancelled_reason == INACTIVE_SUBSCRIPTION_REASON
        # blank cancelled_by is what marks this as the system, not an operator
        assert scheduled.cancelled_by == ''

    def test_leaves_an_active_subscription_alone(self):
        scheduled = self.schedule(send_date=in_days(30))

        cancel_scheduled_invoices_for_inactive_subscriptions(self.domain_obj.name)

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.PENDING

    def test_a_paused_subscription_stops_a_send_due_today(self):
        scheduled = self.schedule(send_date=datetime.date.today())
        self.deactivate_subscription()

        process_scheduled_prepayment_invoices_for_domain(self.domain_obj.name)

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED
        assert not self.get_invoices().exists()

    def test_notifies_accounting_five_days_ahead(self):
        scheduled = self.schedule(send_date=in_days(5))

        notify_upcoming_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        scheduled.refresh_from_db()
        assert scheduled.notified_accounting
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == (
            f'A prepayment invoice for {self.domain_obj.name} '
            f'is scheduled to be sent on {in_days(5).isoformat()}'
        )

    def test_does_not_notify_six_days_ahead(self):
        scheduled = self.schedule(send_date=in_days(6))

        notify_upcoming_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        scheduled.refresh_from_db()
        assert not scheduled.notified_accounting
        assert len(mail.outbox) == 0

    def test_notifies_only_once(self):
        self.schedule(send_date=in_days(5))

        notify_upcoming_scheduled_invoices(datetime.date.today(), self.domain_obj.name)
        notify_upcoming_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        assert len(mail.outbox) == 1

    def test_notifies_a_request_that_slipped_past_the_notice_window(self):
        # a missed run should still notify
        self.schedule(send_date=in_days(2))

        notify_upcoming_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        assert len(mail.outbox) == 1

    def test_does_not_notify_a_cancelled_request(self):
        self.schedule(
            send_date=in_days(5),
            status=ScheduledPrepaymentInvoiceStatus.CANCELLED,
        )

        notify_upcoming_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        assert len(mail.outbox) == 0

    def test_the_notice_names_the_amount_and_date(self):
        self.schedule(send_date=in_days(5))

        notify_upcoming_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        body = mail.outbox[0].body
        assert '12000' in body
        assert in_days(5).isoformat() in body
        assert '12 month prepayment' in body

    def test_does_not_send_a_request_in_another_domain(self):
        other = self.schedule_in_another_domain(send_date=datetime.date.today())

        generate_due_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        other.refresh_from_db()
        assert other.status == ScheduledPrepaymentInvoiceStatus.PENDING
        assert not WirePrepaymentInvoice.objects.filter(
            domain=self.other_domain_obj.name
        ).exists()

    def test_does_not_notify_for_a_request_in_another_domain(self):
        other = self.schedule_in_another_domain(send_date=in_days(5))

        notify_upcoming_scheduled_invoices(datetime.date.today(), self.domain_obj.name)

        other.refresh_from_db()
        assert not other.notified_accounting
        assert len(mail.outbox) == 0

    def test_does_not_cancel_a_request_in_another_domain(self):
        other = self.schedule_in_another_domain(send_date=in_days(30))
        self.deactivate_subscription(self.other_subscription)

        cancel_scheduled_invoices_for_inactive_subscriptions(self.domain_obj.name)

        other.refresh_from_db()
        assert other.status == ScheduledPrepaymentInvoiceStatus.PENDING

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

    def schedule_in_another_domain(self, **overrides):
        return self.schedule(
            domain=self.other_domain_obj.name,
            subscription=self.other_subscription,
            **overrides,
        )

    def get_invoices(self):
        return WirePrepaymentInvoice.objects.filter(domain=self.domain_obj.name)

    def deactivate_subscription(self, subscription=None):
        subscription = subscription or self.subscription
        Subscription.visible_objects.filter(id=subscription.id).update(is_active=False)

    def pause_subscription(self):
        paused = generator.subscribable_plan_version(SoftwarePlanEdition.PAUSED)
        Subscription.visible_objects.filter(id=self.subscription.id).update(
            plan_version=paused
        )
