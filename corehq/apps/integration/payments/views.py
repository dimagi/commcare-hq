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
from corehq.apps.users.models import WebUser
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action
from corehq.apps.integration.payments.services import verify_payment_cases
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.forms import PaymentConfigureForm


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

    @property
    def page_context(self):
        return {
            'has_config': MoMoConfig.objects.filter(domain=self.domain).exists(),
            'config_url': reverse(
                'momo_configuration', args=(self.domain,),
            )
        }


@method_decorator(login_required, name='dispatch')
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
class PaymentsVerificationTableView(HqHtmxActionMixin, SelectablePaginatedTableView):
    urlname = 'payments_verify_table'
    table_class = PaymentsVerifyTable

    def get_queryset(self):
        return CaseSearchES().domain(self.request.domain).case_type(MOMO_PAYMENT_CASE_TYPE)

    @hq_hx_action('post')
    def verify_rows(self, request, *args, **kwargs):
        web_user = WebUser.get_by_username(request.user.username)
        case_ids = request.POST.getlist('selected_ids')

        verified_cases = verify_payment_cases(
            request.domain,
            case_ids=case_ids,
            verifying_user=web_user,
        )
        success_count = len(verified_cases)
        context = {
            'success_count': success_count,
            'failure_count': len(case_ids) - success_count,
        }
        return self.render_htmx_partial_response(
            request,
            'payments/partials/payments_verify_alert.html',
            context,
        )


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
class PaymentConfigurationView(HqHtmxActionMixin, BaseDomainView):
    section_name = _("Data")
    urlname = 'momo_configuration'
    template_name = 'payments/payments_config_base.html'
    page_title = _('Payments Configuration')

    form_class = PaymentConfigureForm
    form_template_partial_name = 'payments/partials/payments_config_form_partial.html'

    @property
    def section_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        return {
            'payments_config_form': self.config_form,
        }

    @property
    def config(self):
        try:
            return MoMoConfig.objects.get(domain=self.domain)
        except MoMoConfig.DoesNotExist:
            return MoMoConfig(domain=self.domain)

    @property
    def config_form(self):
        if self.request.method == 'POST':
            return self.form_class(self.request.POST, instance=self.config)
        return self.form_class(instance=self.config)

    def post(self, request, *args, **kwargs):
        form = self.config_form
        show_success = False
        if form.is_valid():
            form.save()
            show_success = True

        context = {
            'payments_config_form': form,
            'show_success': show_success,
        }
        return self.render_htmx_partial_response(request, self.form_template_partial_name, context)
