import datetime
from decimal import Decimal

from django.urls import reverse

from corehq import privileges
from corehq.apps.accounting.models import (
    ScheduledPrepaymentInvoice,
    ScheduledPrepaymentInvoiceStatus,
    WirePrepaymentBillingRecord,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.tests.utils import in_days
from corehq.apps.accounting.tests.wire_invoice_base import (
    WirePrepaymentTestCase,
)
from corehq.util.test_utils import privilege_enabled


class BasePrepaymentViewTest(WirePrepaymentTestCase):
    def post_prepayment(self, **overrides):
        data = {
            'email_to': 'billing@example.com',
            'email_cc': 'ap@example.com',
            'credit_label': '12 month prepayment',
            'unit_cost': '1000.00',
            'quantity': '12',
            'invoice_amount': '12000.00',
            'prepay_date_start': '2027-01-01',
            'prepay_date_end': '2028-01-01',
        }
        data.update(overrides)
        url = reverse('domain_wire_payment', args=[self.domain_obj.name])
        return self.admin_client.post(url, data)

    def get_invoices(self):
        return WirePrepaymentInvoice.objects.filter(
            domain=self.domain_obj.name
        )

    def get_scheduled(self):
        return ScheduledPrepaymentInvoice.objects.filter(
            domain=self.domain_obj.name
        )


class WirePrepaymentViewTest(BasePrepaymentViewTest):
    def test_creates_invoice_with_posted_amount(self):
        response = self.post_prepayment()

        assert response.status_code == 200
        assert response.json() == {'success': True}
        invoice = self.get_invoices().get()
        assert invoice.balance == Decimal('12000.0000')
        assert invoice.date_start == datetime.date(2027, 1, 1)
        assert invoice.date_end == datetime.date(2028, 1, 1)

    def test_due_date_is_thirty_days_after_generation(self):
        self.post_prepayment()

        invoice = self.get_invoices().get()
        assert invoice.date_due == datetime.date.today() + datetime.timedelta(
            days=30
        )

    def test_emails_the_posted_recipients(self):
        self.post_prepayment()

        record = WirePrepaymentBillingRecord.objects.get(
            invoice=self.get_invoices().get()
        )
        assert set(record.emailed_to_list) == {
            'billing@example.com',
            'ap@example.com',
        }
        assert not record.skipped_email

    def test_rejects_malformed_email(self):
        response = self.post_prepayment(email_to='not an email')

        assert 'error' in response.json()
        assert not self.get_invoices().exists()

    def test_rejects_end_date_before_start_date(self):
        response = self.post_prepayment(
            prepay_date_start='2028-01-01',
            prepay_date_end='2027-01-01',
        )

        assert (
            response.json()['error']['message']
            == 'Prepayment End Date: Prepayment end date must be after start date.'
        )
        assert not self.get_invoices().exists()

    def test_rejects_negative_unit_cost(self):
        response = self.post_prepayment(unit_cost='-5.00')

        assert 'error' in response.json()
        assert not self.get_invoices().exists()

    def test_rejects_negative_quantity(self):
        response = self.post_prepayment(quantity='-1')

        assert 'error' in response.json()
        assert not self.get_invoices().exists()

    def test_invoices_instead_of_scheduling_without_a_send_date(self):
        self.post_prepayment()

        assert self.get_invoices().exists()
        assert not self.get_scheduled().exists()

    def test_rejects_scheduling_without_the_accounting_admin_privilege(self):
        """Scheduling is for accounting admins, not a project's billing admins"""
        response = self.post_prepayment(send_date=in_days(90).isoformat())

        assert response.status_code == 404
        assert not self.get_scheduled().exists()
        assert not self.get_invoices().exists()


@privilege_enabled(privileges.ACCOUNTING_ADMIN)
class SchedulePrepaymentTest(BasePrepaymentViewTest):
    def test_schedules_a_pending_request_for_a_future_send_date(self):
        response = self.post_prepayment(send_date=in_days(90).isoformat())

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

    def test_schedules_instead_of_invoicing(self):
        self.post_prepayment(send_date=in_days(90).isoformat())

        assert not self.get_invoices().exists()

    def test_rejects_a_send_date_in_the_past(self):
        response = self.post_prepayment(send_date=in_days(-1).isoformat())

        assert response.json()['error']['message'] == (
            'Send On: The send date must be in the future.'
        )
        assert not self.get_scheduled().exists()
        assert not self.get_invoices().exists()
