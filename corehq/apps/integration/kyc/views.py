from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from corehq import toggles
from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView
from corehq.apps.integration.kyc.forms import KycConfigureForm
from corehq.apps.integration.kyc.models import (
    KycConfig,
    UserDataStore,
)
from corehq.apps.integration.kyc.tables import KycVerifyTable
from corehq.apps.integration.kyc.services import get_user_data_for_api
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


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

    def get_queryset(self):
        kyc_config = KycConfig.objects.get(domain=self.request.domain)
        row_objs = self._row_data(kyc_config)
        rows = []
        for row_obj in row_objs:
            rows.append(
                self._parse_row(row_obj, kyc_config)
            )
        return rows

    def _row_data(self, kyc_config):
        if kyc_config.user_data_store in [UserDataStore.CUSTOM_USER_DATA, UserDataStore.USER_CASE]:
            return CommCareUser.by_domain(self.request.domain)
        elif kyc_config.user_data_store == UserDataStore.OTHER_CASE_TYPE:
            case_ids = (
                CaseSearchES()
                .domain(self.request.domain)
                .case_type(kyc_config.other_case_type)
            ).get_ids()
            return CommCareCase.objects.get_cases(case_ids, self.request.domain)

    def _parse_row(self, row_obj, config):
        user_data = get_user_data_for_api(row_obj, config)
        row_id = row_obj.user_id if isinstance(row_obj, CommCareUser) else row_obj.case_id
        row_data = {
            'id': row_id,
            'has_invalid_data': False,
        }
        user_fields = (
            'first_name',
            'last_name',
            'phone_number',
            'email',
            'national_id_number',
            'street_address',
            'city',
            'post_code',
            'country',
        )
        system_fields = (
            'kyc_is_verified',
            'kyc_last_verified_at',
        )
        for field in user_fields:
            if field not in user_data:
                row_data['has_invalid_data'] = True
                continue
            row_data[field] = user_data[field]
        for field in system_fields:
            row_data[field] = user_data.get(field)
        return row_data

    @hq_hx_action('post')
    def verify_rows(self, request, *args, **kwargs):
        verify_all = request.POST.get('verify_all')
        verify_success = True
        success_count = 0
        fail_count = 0
        if verify_all:
            # TODO: Need to get all IDS. Could take inspiration from _row_data to fetch all IDs
            # TODO: Verify all rows
            pass
        else:
            pass
            # TODO: Verify selected rows
            # selected_ids = request.POST.getlist('selected_ids')

        context = {
            'verify_success': verify_success,
            'success_count': success_count,
            'fail_count': fail_count,
        }
        return self.render_htmx_partial_response(request, 'kyc/partials/kyc_verify_alert.html', context)


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
