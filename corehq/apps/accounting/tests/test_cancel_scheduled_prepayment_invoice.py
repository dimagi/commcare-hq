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


    def test_cancels_a_pending_request(self):
        scheduled = ScheduledPrepaymentInvoice.objects.create(
            domain=self.domain_obj.name,
            subscription=self.subscription,
            send_date=datetime.date.today() + datetime.timedelta(days=45),
            amount=Decimal('3000.00'),
            credit_label='Installment 3 of 4',
            unit_cost=Decimal('1000.00'),
            quantity=3,
            contact_emails=['billing@example.com'],
            cc_emails=[],
            date_start=datetime.date(2027, 7, 1),
            date_end=datetime.date(2027, 10, 1),
            created_by=self.username,
        )

        response = self.admin_client.post(
            reverse(CancelScheduledInvoiceView.urlname, args=[scheduled.id]),
            {'reason': 'Superseded by a renegotiated contract'},
        )

        assert response.status_code == 302
        scheduled.refresh_from_db()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.CANCELLED
        assert scheduled.cancelled_by == self.username
        assert scheduled.cancelled_reason == 'Superseded by a renegotiated contract'
