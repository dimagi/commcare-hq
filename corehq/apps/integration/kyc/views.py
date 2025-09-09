from functools import cached_property

from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from memoized import memoized

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.es import filters
from corehq.apps.es.case_search import (
    case_property_missing,
    case_property_query,
)
from corehq.apps.es.users import (
    missing_or_empty_user_data_property,
    query_user_data,
)
from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView
from corehq.apps.integration.kyc.filters import KycVerificationStatusFilter
from corehq.apps.integration.kyc.forms import KycConfigureForm
from corehq.apps.integration.kyc.models import (
    KycConfig,
    KycVerificationStatus,
    UserDataStore,
)
from corehq.apps.integration.kyc.services import verify_users
from corehq.apps.integration.kyc.tables import (
    KycCaseElasticRecord,
    KycUserElasticRecord,
    KycVerifyTable,
)
from corehq.apps.reports.generic import get_filter_classes
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action
from corehq.util.metrics import metrics_counter, metrics_gauge
from corehq.util.timezones.utils import get_timezone


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


@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.KYC_VERIFICATION.required_decorator(), name='dispatch')
class KycVerificationTableView(HqHtmxActionMixin, SelectablePaginatedTableView):
    urlname = 'kyc_verify_table'
    table_class = KycVerifyTable

    @cached_property
    def kyc_config(self):
        return KycConfig.objects.get(domain=self.request.domain)

    def get_table_kwargs(self):
        orderable = True
        if self.kyc_config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
            record_class = KycUserElasticRecord
            orderable = False
        else:
            record_class = KycCaseElasticRecord
        self.table_class.record_class = record_class

        return {
            'extra_columns': KycVerifyTable.get_extra_columns(self.kyc_config),
            'record_kwargs': {'kyc_config': self.kyc_config},
            'orderable': orderable,
        }

    def get_queryset(self):
        query = self.kyc_config.get_kyc_users_query()
        return self._apply_filters(query)

    def _apply_filters(self, query):
        query_filters = []
        if kyc_verification_status := self.request.GET.get(KycVerificationStatusFilter.slug):
            self._apply_kyc_verification_status_filter(kyc_verification_status, query_filters)
        if query_filters:
            query = query.filter(filters.AND(*query_filters))
        return query

    def _apply_kyc_verification_status_filter(self, kyc_verification_status, query_filters):
        field_name = 'kyc_verification_status'
        if kyc_verification_status == 'pending':
            if self.kyc_config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
                query_filters.append(missing_or_empty_user_data_property(field_name))
            else:
                query_filters.append(case_property_missing(field_name))
        else:
            if self.kyc_config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
                query_filters.append(query_user_data(field_name, kyc_verification_status))
            else:
                query_filters.append(case_property_query(field_name, kyc_verification_status))

    @hq_hx_action('post')
    def verify_rows(self, request, *args, **kwargs):
        if request.POST.get('verify_all') == 'true':
            kyc_users = list(self.kyc_config.get_all_kyc_users())
        else:
            selected_ids = request.POST.getlist('selected_ids')
            kyc_users = list(self.kyc_config.get_kyc_users_by_ids(selected_ids))
        kyc_users = self._filter_valid_users(kyc_users)

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

    def _filter_valid_users(self, kyc_users):
        def is_user_valid(kyc_user):
            return all(kyc_user.get(field) for field in kyc_user_api_fields)

        kyc_user_api_fields = self.kyc_config.get_api_field_to_user_data_map_values().values()
        return [kyc_user for kyc_user in kyc_users if is_user_valid(kyc_user)]

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


class KYCFiltersMixin:

    fields = [
        'corehq.apps.integration.kyc.filters.KycVerificationStatusFilter',
    ]

    def filters_context(self):
        return {
            'report': {
                'title': self.page_title,
                'section_name': self.section_name,
                'show_filters': True,
            },
            'report_filters': [
                dict(field=f.render(), slug=f.slug) for f in self.filter_classes
            ],
            'report_filter_form_action_css_class': CSS_ACTION_CLASS,
        }

    @property
    @memoized
    def filter_classes(self):
        timezone = get_timezone(self.request, self.domain)
        return get_filter_classes(self.fields, self.request, self.domain, timezone, use_bootstrap5=True)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.KYC_VERIFICATION.required_decorator(), name='dispatch')
class KycVerificationReportView(BaseDomainView, KYCFiltersMixin):
    urlname = 'kyc_verify'
    template_name = 'kyc/kyc_verify_report.html'
    section_name = _('Data')
    page_title = _('KYC Report')

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'domain_has_config': self.domain_has_config,
            **self.filters_context(),
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
            metrics_gauge(
                'commcare.integration.kyc.total_users.count',
                kyc_config.get_kyc_users_count(),
                tags={'domain': self.domain}
            )
