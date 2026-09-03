import datetime
from decimal import Decimal

from django.urls import reverse

from corehq.apps.accounting.models import (
    WirePrepaymentBillingRecord,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.tests.wire_invoice_base import (
    WirePrepaymentTestCase,
)


class WirePrepaymentViewTest(WirePrepaymentTestCase):
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
