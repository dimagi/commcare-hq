from functools import cached_property

from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from corehq import toggles
from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView
from corehq.apps.integration.kyc.forms import KycConfigureForm
from corehq.apps.integration.kyc.models import KycConfig, KycVerificationStatus
from corehq.apps.integration.kyc.services import verify_users
from corehq.apps.integration.kyc.tables import KycVerifyTable
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action
from corehq.util.metrics import metrics_counter, metrics_gauge


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.KYC_VERIFICATION.required_decorator(), name='dispatch')
class KycConfigurationView(HqHtmxActionMixin, BaseDomainView):
    section_name = _("Data")
    urlname = 'kyc_configuration'
    template_name = 'kyc/kyc_config_base.html'
    page_title = _('KYC Configuration')

    form_class = KycConfigureForm
    form_template_partial_name = 'kyc/partials/kyc_config_form_partial.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def page_context(self):
        return {
            'kyc_config_form': self.config_form,
        }

    @property
    def config(self):
        try:
            # Currently a domain can only save one config so we shouldn't
            # expect more than one per domain
            return KycConfig.objects.get(domain=self.domain)
        except KycConfig.DoesNotExist:
            return KycConfig(domain=self.domain)

    @property
    def config_form(self):
        if self.request.method == 'POST':
            return self.form_class(self.request.POST, instance=self.config)
        return self.form_class(instance=self.config)

    def post(self, request, *args, **kwargs):
        form = self.config_form
        show_success = False
        if form.is_valid():
            form.save(commit=True)
            show_success = True

        context = {
            'kyc_config_form': form,
            'show_success': show_success,
        }
        return self.render_htmx_partial_response(request, self.form_template_partial_name, context)


@method_decorator(login_required, name='dispatch')
@method_decorator(toggles.KYC_VERIFICATION.required_decorator(), name='dispatch')
class KycVerificationTableView(HqHtmxActionMixin, SelectablePaginatedTableView):
    urlname = 'kyc_verify_table'
    table_class = KycVerifyTable

    @cached_property
    def kyc_config(self):
        return KycConfig.objects.get(domain=self.request.domain)

    def get_table_kwargs(self):
        return {
            'extra_columns': KycVerifyTable.get_extra_columns(self.kyc_config),
        }

    def get_queryset(self):
        kyc_users = self.kyc_config.get_kyc_users()
        return [self._parse_row(kyc_user) for kyc_user in kyc_users]

    def _parse_row(self, kyc_user):
        row_data = {
            'id': kyc_user.user_id,
            'has_invalid_data': False,
            'kyc_verification_status': kyc_user.get('kyc_verification_status'),
            'kyc_last_verified_at': kyc_user.get('kyc_verification_status'),
        }
        for field in self.kyc_config.api_field_to_user_data_map.values():
            value = kyc_user.get(field)
            if not value:
                row_data['has_invalid_data'] = True
            else:
                row_data[field] = value
        return row_data

    @hq_hx_action('post')
    def verify_rows(self, request, *args, **kwargs):
        if request.POST.get('verify_all') == 'true':
            kyc_users = self.kyc_config.get_kyc_users()
        else:
            selected_ids = request.POST.getlist('selected_ids')
            kyc_users = self.kyc_config.get_kyc_users_by_ids(selected_ids)
        existing_failed_user_ids = self._get_existing_failed_users(kyc_users)
        results = verify_users(kyc_users, self.kyc_config)
        success_count = sum(1 for result in results.values() if result == KycVerificationStatus.PASSED)
        failure_count = len(results) - success_count
        context = {
            'success_count': success_count,
            'failure_count': failure_count,
        }

        self._report_success_on_reverification_metric(existing_failed_user_ids, results)

        return self.render_htmx_partial_response(request, 'kyc/partials/kyc_verify_alert.html', context)

    def _report_success_on_reverification_metric(self, existing_failed_user_ids, results):
        successful_user_ids = [user_id for user_id, status in results.items() if status is True]
        reverification_success_count = len(set(existing_failed_user_ids) & set(successful_user_ids))
        if reverification_success_count:
            metrics_counter(
                'commcare.integration.kyc.reverification.success.count',
                reverification_success_count,
                tags={'domain': self.request.domain}
            )

    def _get_existing_failed_users(self, kyc_users):
        return [
            kyc_user.user_id for kyc_user in kyc_users
            if kyc_user.kyc_verification_status == KycVerificationStatus.FAILED
        ]


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.KYC_VERIFICATION.required_decorator(), name='dispatch')
class KycVerificationReportView(BaseDomainView):
    urlname = 'kyc_verify'
    template_name = 'kyc/kyc_verify_report.html'
    section_name = _('Data')
    page_title = _('KYC Report')

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'domain_has_config': self.domain_has_config,
        })
        return context

    @property
    def domain_has_config(self):
        return KycConfig.objects.filter(domain=self.domain).exists()

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))

    def get(self, request, *args, **kwargs):
        self._report_users_count_metric()
        return super().get(request, *args, **kwargs)

    def _report_users_count_metric(self):
        if self.domain_has_config:
            kyc_config = KycConfig.objects.get(domain=self.domain)
            total_users = len(kyc_config.get_kyc_users())
            metrics_gauge(
                'commcare.integration.kyc.total_users.count',
                total_users,
                tags={'domain': self.domain}
            )
