from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from corehq import toggles
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
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))


@method_decorator(login_required, name='dispatch')
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
class PaymentsVerificationTableView(HqHtmxActionMixin, SelectablePaginatedTableView):
    urlname = 'payments_verify_table'
    table_class = PaymentsVerifyTable

    def get_queryset(self):
        # TODO Get all cases with the relevant case type
        # TODO Should only fetch required objects w.r.t pagination
        # row_objs = []
        # rows = []
        # for row_obj in row_objs:
        #     rows.append(
        #         self._parse_row(row_obj)
        #     )
        # return rows
        return CaseSearchES().domain(self.request.domain).case_type('case-01')

    def _parse_row(self, row_obj):
        row_data = {
            'id': row_obj.case_id,
            'has_invalid_data': False,
        }
        user_fields = [
            'batch_number',
            'user_or_case_id',
            'phone_number',
            'email',
            'amount',
            'currency',
            'payee_note',
            'payer_message',
        ]
        for field in user_fields:
            if field not in row_obj:
                row_data['has_invalid_data'] = True
                continue
            row_data[field] = row_obj[field]
        return row_data
