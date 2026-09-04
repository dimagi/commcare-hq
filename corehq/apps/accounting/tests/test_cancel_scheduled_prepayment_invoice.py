import datetime
from decimal import Decimal

from django.urls import reverse

from django_prbac.models import Grant, Role, UserRole

from corehq import privileges
from corehq.apps.accounting.models import (
    ScheduledPrepaymentInvoice,
    ScheduledPrepaymentInvoiceStatus,
)
from corehq.apps.accounting.tests.wire_invoice_base import (
    WirePrepaymentTestCase,
)
from corehq.apps.accounting.views import CancelScheduledInvoiceView


class CancelScheduledInvoiceTest(WirePrepaymentTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # AccountingSectionView requires a superuser holding ACCOUNTING_ADMIN,
        # granted through the operations team role
        django_user = cls.web_user.get_django_user()
        django_user.is_superuser = True
        django_user.save()

        ops_role, _ = Role.objects.get_or_create(
            slug=privileges.OPERATIONS_TEAM, defaults={'name': 'Ops'}
        )
        accounting_role, _ = Role.objects.get_or_create(
            slug=privileges.ACCOUNTING_ADMIN, defaults={'name': 'Accounting'}
        )
        Grant.objects.get_or_create(from_role=ops_role, to_role=accounting_role)
        user_privs = Role.objects.create(
            slug=f'{django_user.username}_privs', name='Test user privileges'
        )
        UserRole.objects.create(user=django_user, role=user_privs)
        Grant.objects.create(from_role=user_privs, to_role=ops_role)
        Role.update_cache()

    def schedule(self, **overrides):
        kwargs = {
            'domain': self.domain_obj.name,
            'subscription': self.subscription,
            'send_date': datetime.date.today() + datetime.timedelta(days=45),
            'amount': Decimal('3000.00'),
            'credit_label': 'Installment 3 of 4',
            'unit_cost': Decimal('1000.00'),
            'quantity': 3,
            'contact_emails': ['billing@example.com'],
            'cc_emails': [],
            'date_start': datetime.date(2027, 7, 1),
            'date_end': datetime.date(2027, 10, 1),
            'created_by': self.username,
        }
        kwargs.update(overrides)
        return ScheduledPrepaymentInvoice.objects.create(**kwargs)

    def cancel(self, scheduled, reason='Superseded by a renegotiated contract'):
        return self.admin_client.post(
            reverse(CancelScheduledInvoiceView.urlname, args=[scheduled.id]),
            {'reason': reason},
        )

    def test_cancels_a_pending_request(self):
        scheduled = self.schedule()

        response = self.cancel(scheduled)

        assert response.status_code == 302
        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED
        assert scheduled.cancelled_by == self.username
        assert scheduled.cancelled_reason == 'Superseded by a renegotiated contract'

    def test_requires_a_reason(self):
        scheduled = self.schedule()

        response = self.cancel(scheduled, reason='')

        assert response.status_code == 200  # form redisplayed, not redirected
        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.PENDING
        assert scheduled.cancelled_by == ''

    def test_will_not_cancel_one_that_already_sent(self):
        scheduled = self.schedule(status=ScheduledPrepaymentInvoiceStatus.SENT)

        self.cancel(scheduled)

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.SENT
        assert scheduled.cancelled_by == ''

    def test_does_not_overwrite_an_earlier_cancellation(self):
        scheduled = self.schedule()
        self.cancel(scheduled, reason='the original reason')

        self.cancel(scheduled, reason='a later reason')

        scheduled.refresh_from_db()
        assert scheduled.cancelled_reason == 'the original reason'

    def test_a_cancelled_request_never_sends(self):
        from corehq.apps.accounting.tasks import generate_due_scheduled_invoices

        scheduled = self.schedule(send_date=datetime.date.today())
        self.cancel(scheduled)

        generate_due_scheduled_invoices(
            datetime.date.today(), self.domain_obj.name
        )

        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED
        assert scheduled.invoice_id is None
