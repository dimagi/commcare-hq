from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from memoized import memoized

from corehq import toggles
from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.es import CaseSearchES, filters
from corehq.apps.es.case_search import (
    case_property_query,
    wrap_case_search_hit,
)
from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView
from corehq.apps.integration.kyc.models import KycConfig
from corehq.apps.integration.payments.const import PaymentProperties, PaymentStatus
from corehq.apps.integration.payments.forms import PaymentConfigureForm
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.services import verify_payment_cases
from corehq.apps.integration.payments.tables import PaymentsVerifyTable
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF
from corehq.apps.reports.generic import get_filter_classes
from corehq.apps.reports.standard.cases.utils import add_case_owners_and_location_access
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions, WebUser
from corehq.apps.users.permissions import PAYMENTS_REPORT_PERMISSION
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action
from corehq.util.timezones.utils import get_timezone


class PaymentsFiltersMixin:
    fields = [
        'corehq.apps.integration.payments.filters.PaymentCaseListFilter',
        'corehq.apps.integration.payments.filters.BatchNumberFilter',
        'corehq.apps.integration.payments.filters.PaymentVerifiedByFilter',
        'corehq.apps.integration.payments.filters.PaymentStatusFilter',
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


require_payments_report_access = require_permission(
    HqPermissions.view_report,
    PAYMENTS_REPORT_PERMISSION,
    login_decorator=None
)


@location_safe
@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
@method_decorator(require_payments_report_access, name='dispatch')
class PaymentsVerificationReportView(BaseDomainView, PaymentsFiltersMixin):
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
            ),
            **self.filters_context(),
        }


@location_safe
@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
@method_decorator(require_payments_report_access, name='dispatch')
class PaymentsVerificationTableView(HqHtmxActionMixin, SelectablePaginatedTableView):
    urlname = 'payments_verify_table'
    table_class = PaymentsVerifyTable

    def get_queryset(self):
        query = CaseSearchES().domain(self.request.domain).case_type(MOMO_PAYMENT_CASE_TYPE)
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)
        query = add_case_owners_and_location_access(
            query,
            self.request.domain,
            self.request.couch_user,
            self.request.can_access_all_locations,
            mobile_user_and_group_slugs
        )
        query = self._apply_filters(query)
        return query

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        context_data['verification_statuses'] = self._get_verification_status(
            context_data['page_obj'].object_list
        )

        return context_data

    def _get_verification_status(self, object_list):
        if not self.kyc_config:
            return {}

        user_or_case_ids = self._get_user_or_case_ids(object_list)
        kyc_users = self.kyc_config.get_kyc_users_by_ids(user_or_case_ids)
        return {
            kyc_user.user_id: kyc_user.kyc_verification_status
            for kyc_user in kyc_users
        }

    @cached_property
    def kyc_config(self):
        try:
            return KycConfig.objects.get(domain=self.request.domain)
        except KycConfig.DoesNotExist:
            return None

    @staticmethod
    def _get_user_or_case_ids(object_list):
        user_or_case_ids = []
        for commcare_payment_case_details in object_list:
            case = wrap_case_search_hit(commcare_payment_case_details)
            if user_or_case_id := case.get_case_property(PaymentProperties.USER_OR_CASE_ID):
                user_or_case_ids.append(user_or_case_id)
        return user_or_case_ids

    def _apply_filters(self, query):
        query_filters = []

        if batch_number := self.request.GET.get('batch_number'):
            query_filters.append(case_property_query(PaymentProperties.BATCH_NUMBER, batch_number))

        if verified_by := self.request.GET.get('verified_by'):
            query_filters.append(case_property_query(PaymentProperties.PAYMENT_VERIFIED_BY, verified_by))

        if payment_status := self.request.GET.get('payment_status'):
            # For new payment cases that are not verified yet, the case property does not exist,
            # hence the check for '' (empty string).
            if payment_status == PaymentStatus.NOT_VERIFIED.value:
                query_filters.append(filters.OR(
                    case_property_query(PaymentProperties.PAYMENT_STATUS, ''),
                    case_property_query(PaymentProperties.PAYMENT_STATUS, payment_status)
                ))
            else:
                query_filters.append(case_property_query(PaymentProperties.PAYMENT_STATUS, payment_status))
        if query_filters:
            query = query.filter(filters.AND(*query_filters))

        return query

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
@method_decorator(require_payments_report_access, name='dispatch')
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
