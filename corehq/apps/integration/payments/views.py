from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from corehq import toggles
from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE
from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.es import CaseSearchES
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView
from corehq.apps.integration.payments.tables import PaymentsVerifyTable
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
class PaymentsVerificationReportView(BaseDomainView):
    urlname = 'payments_verify'
    template_name = 'payments/payments_verify_report.html'
    section_name = _('Data')
    page_title = _('Payments Verification Report')

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))


@method_decorator(login_required, name='dispatch')
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
class PaymentsVerificationTableView(HqHtmxActionMixin, SelectablePaginatedTableView):
    urlname = 'payments_verify_table'
    table_class = PaymentsVerifyTable

    def get_queryset(self):
        return CaseSearchES().domain(self.request.domain).case_type(MOMO_PAYMENT_CASE_TYPE)

    @hq_hx_action('post')
    def verify_rows(self, request, *args, **kwargs):
        # TODO Verify payments to be done in a followup ticket
        success_count = 0
        failure_count = 0
        context = {
            'success_count': success_count,
            'failure_count': failure_count,
        }
        return self.render_htmx_partial_response(
            request,
            'payments/partials/payments_verify_alert.html',
            context,
        )
