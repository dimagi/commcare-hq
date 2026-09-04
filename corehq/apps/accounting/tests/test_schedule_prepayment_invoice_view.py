import datetime
from decimal import Decimal

from django.urls import reverse

from corehq import privileges
from corehq.apps.accounting.models import (
    ScheduledPrepaymentInvoice,
    ScheduledPrepaymentInvoiceStatus,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.tests.utils import in_days
from corehq.apps.accounting.tests.wire_invoice_base import (
    WirePrepaymentTestCase,
)
from corehq.util.test_utils import privilege_enabled



@privilege_enabled(privileges.ACCOUNTING_ADMIN)
class SchedulePrepaymentInvoiceViewTest(WirePrepaymentTestCase):
    def post_schedule(self, **overrides):
        data = {
            'email_to': 'billing@example.com',
            'email_cc': 'ap@example.com',
            'credit_label': '12 month prepayment',
            'unit_cost': '1000.00',
            'quantity': '12',
            'invoice_amount': '12000.00',
            'prepay_date_start': '2027-01-01',
            'prepay_date_end': '2028-01-01',
            'send_date': in_days(90).isoformat(),
        }
        data.update(overrides)
        url = reverse(
            'domain_schedule_prepayment_invoice', args=[self.domain_obj.name]
        )
        return self.admin_client.post(url, data)

    def get_scheduled(self):
        return ScheduledPrepaymentInvoice.objects.filter(
            domain=self.domain_obj.name
        )

    def test_creates_a_pending_request(self):
        response = self.post_schedule()

        assert response.status_code == 200
        assert response.json()['success'] is True
        assert response.json()['send_date'] == in_days(90).isoformat()

        scheduled = self.get_scheduled().get()
        assert scheduled.status == ScheduledPrepaymentInvoiceStatus.PENDING
        assert scheduled.send_date == in_days(90)
        assert scheduled.amount == Decimal('12000.0000')
        assert scheduled.unit_cost == Decimal('1000.0000')
        assert scheduled.quantity == 12
        assert scheduled.credit_label == '12 month prepayment'
        assert scheduled.contact_emails == ['billing@example.com']
        assert scheduled.cc_emails == ['ap@example.com']
        assert scheduled.date_start == datetime.date(2027, 1, 1)
        assert scheduled.date_end == datetime.date(2028, 1, 1)
        assert scheduled.subscription == self.subscription

    def test_invoice_is_not_created(self):
        self.post_schedule()

        assert not WirePrepaymentInvoice.objects.filter(
            domain=self.domain_obj.name
        ).exists()

    def test_rejects_a_past_send_date(self):
        response = self.post_schedule(send_date=in_days(-1).isoformat())

        assert (
            response.json()['error']['message']
            == 'Send On: The send date must be in the future.'
        )
        assert not self.get_scheduled().exists()

    def test_accepts_a_send_date_of_tomorrow(self):
        response = self.post_schedule(send_date=in_days(1).isoformat())

        assert response.json()['success'] is True

    def test_rejects_a_send_date_of_today(self):
        response = self.post_schedule(
            send_date=datetime.date.today().isoformat()
        )

        assert 'error' in response.json()
        assert not self.get_scheduled().exists()

    def test_rejects_credit_label_that_is_too_long(self):
        response = self.post_schedule(credit_label='x' * 257)

        assert 'error' in response.json()
        assert not self.get_scheduled().exists()

    def test_accepts_a_credit_label_at_the_limit(self):
        response = self.post_schedule(credit_label='x' * 256)

        assert response.json()['success'] is True


class SchedulePrepaymentInvoicePermissionTest(WirePrepaymentTestCase):
    """Scheduling is for accounting admins, not a project's billing admins"""

    def test_rejects_a_billing_admin_without_accounting_admin(self):
        url = reverse(
            'domain_schedule_prepayment_invoice', args=[self.domain_obj.name]
        )

        response = self.admin_client.post(url, {})

        assert response.status_code == 404
        assert not ScheduledPrepaymentInvoice.objects.exists()
