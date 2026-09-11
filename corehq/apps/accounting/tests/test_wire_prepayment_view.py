from django.urls import reverse

from corehq import privileges
from corehq.apps.accounting.models import (
    ScheduledPrepaymentInvoice,
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
    def test_reports_a_generated_invoice(self):
        response = self.post_prepayment()

        assert response.status_code == 200
        assert response.json() == {'success': True}
        assert self.get_invoices().exists()

    def test_reports_form_errors_as_one_message(self):
        response = self.post_prepayment(
            prepay_date_start='2028-01-01',
            prepay_date_end='2027-01-01',
        )

        assert (
            response.json()['error']['message']
            == 'Prepayment End Date: Prepayment end date must be after start date.'
        )
        assert not self.get_invoices().exists()

    def test_rejects_scheduling_without_the_accounting_admin_privilege(self):
        """Scheduling is for accounting admins, not a project's billing admins"""
        response = self.post_prepayment(send_date=in_days(90).isoformat())

        assert response.status_code == 404
        assert not self.get_scheduled().exists()
        assert not self.get_invoices().exists()


@privilege_enabled(privileges.ACCOUNTING_ADMIN)
class SchedulePrepaymentTest(BasePrepaymentViewTest):
    def test_reports_the_date_a_scheduled_invoice_will_send(self):
        response = self.post_prepayment(send_date=in_days(90).isoformat())

        assert response.status_code == 200
        assert response.json() == {
            'success': True,
            'send_date': in_days(90).isoformat(),
        }
        assert self.get_scheduled().exists()
        assert not self.get_invoices().exists()
