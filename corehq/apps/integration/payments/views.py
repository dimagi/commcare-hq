from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from memoized import memoized

from corehq import toggles
from corehq.apps.es.case_search import case_property_query
from corehq.util.timezones.utils import get_timezone
from corehq.apps.reports.generic import get_filter_classes
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
from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS
from corehq.apps.integration.payments.filters import PaymentVerificationStatusFilter, PaymentStatus
from corehq.apps.integration.payments.const import PaymentProperties


class PaymentsFiltersMixin:
    fields = [
        'corehq.apps.integration.payments.filters.PaymentVerificationStatusFilter',
        'corehq.apps.integration.payments.filters.BatchNumberFilter',
        'corehq.apps.integration.payments.filters.PaymentVerifiedByFilter',
        'corehq.apps.integration.payments.filters.PaymentStatus',
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
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
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


@method_decorator(login_required, name='dispatch')
@method_decorator(toggles.MTN_MOBILE_WORKER_VERIFICATION.required_decorator(), name='dispatch')
class PaymentsVerificationTableView(HqHtmxActionMixin, SelectablePaginatedTableView):
    urlname = 'payments_verify_table'
    table_class = PaymentsVerifyTable

    def get_queryset(self):
        query = CaseSearchES().domain(self.request.domain).case_type(MOMO_PAYMENT_CASE_TYPE)

        if verification_status := self.request.GET.get('payment_verification_status'):
            filter_value = 'True' if verification_status == PaymentVerificationStatusFilter.verified else ''
            query = query.filter(case_property_query(PaymentProperties.PAYMENT_VERIFIED, filter_value))

        if batch_numer := self.request.GET.get('batch_number'):
            query = query.filter(case_property_query(PaymentProperties.BATCH_NUMBER, batch_numer))

        if verified_by := self.request.GET.get('verified_by'):
            query = query.filter(case_property_query(PaymentProperties.PAYMENT_VERIFIED_BY, verified_by))

        if payment_status := self.request.GET.get('payment_status'):
            if payment_status == PaymentStatus.submitted:
                filter_value = 'True'
            elif payment_status == PaymentStatus.submission_failed:
                filter_value = 'False'
            else:
                filter_value = ''
            query = query.filter(case_property_query(PaymentProperties.PAYMENT_SUBMITTED, filter_value))

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
