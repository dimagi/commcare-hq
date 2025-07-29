import io
import re
from itertools import chain

from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTableData, ElasticTable
from corehq.apps.reports.cache import request_cache
from couchexport.export import export_from_tables
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.web import json_request
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


from django.http import HttpResponse


class TableExportConfig:
    """
    Configuration for export functionality.
    Attributes:
        exportable_all (bool): If True, export all rows, otherwise export only the rows shown in the table.
        export_format (str): Override to set the export format from backend. Defaults to XLS_2007.
        export_file_name (str): Name for the exported file (without extension). Defaults to the class name.
        export_sheet_name (str): Name for the worksheet. Defaults to export_name
    """
    exportable_all = False
    export_format = None
    export_file_name = None
    export_sheet_name = None

    EXPORT_CONFIG_KEYS = {"exportable_all", "export_file_name", "export_format", "export_sheet_name"}

    @memoized
    def get_export_sheet_name(self):
        return self.export_sheet_name or self.get_export_name()

    @memoized
    def get_export_name(self):
        return self.export_file_name or self.__class__.__name__

    @memoized
    def get_export_format(self):
        return self.export_format or self.request.GET.get('format', Format.XLS_2007)

    def config_as_dict(self):
        return { key: getattr(self, key) for key in self.EXPORT_CONFIG_KEYS }

from django_tables2.views import SingleTableMixin
class TableExportMixin(TableExportConfig, SingleTableMixin):
    """
    Mixin to add export functionality to django-tables2 based views.
    Similar to django-tables2's  but using HQ's export implementation instead of tablib.
    Attributes:
        is_cacheable: (bool): If True, the export can be cached. Applicable for only current page export. Defaults to True.
        report_title (str): Title of the report. Defaults to the class name.
        exclude_columns_in_export (tuple): Columns to exclude from the export. Defaults to empty tuple.
    Usage:
        - Inherit this mixin in a view that uses django-tables2.
        - Define `table_class` as the django-tables2 table class to use.
        - Implement `get_queryset()` method to provide the data for the table.
        - Optionally set `exportable_all` to True if you want to export all rows instead of just the current page.
        - Optionally set `export_format`, `export_name`, and `export_sheet_name` to customize export behavior.
        - Trigger export by calling the `trigger_export()` method.
    """
    report_title = None
    is_cacheable = True
    exclude_columns_in_export = ()

    # TODO Optional Validate the class inheriting this mixin has request, domain and django table class.

    # TODO Should work for all types of data

    @memoized
    def get_report_title(self):
        return self.report_title or self.__class__.__name__


    def get_table_for_export(self):
        """
        Returns the table to be exported.
        This method can be overridden to customize the table used for export.
        """
        if self.exportable_all:
            self.table_pagination = False
            table =  self.table_class(data=self.get_table_data())
            if isinstance(table, ElasticTable):
                table.request = self.request
                table.data = table.data.get_all_records()
            return table
        return super().get_table()

    @property
    def export_table(self):
        """
        Returns data in the format expected by export_from_tables:
        [[sheet_name, [headers, row1, row2, ...]]]
        """
        def _unformat_row(row):
            return [self._strip_tags(val) for val in row]
        if self.exportable_all:
            self.table_pagination = False

        table = self.get_table_for_export()
        rows_iter = table.as_values(exclude_columns=self.exclude_columns_in_export)
        print("Total rows in the table for export", len(list(rows_iter)))
        header_row = next(rows_iter)
        formatted_rows = (_unformat_row(row) for row in rows_iter)
        table = chain([header_row], formatted_rows)
        return [[self.get_export_sheet_name(), table]]

    # TODO Move this to a utility module if used elsewhere
    @staticmethod
    def _strip_tags(value):
        """
        Strip HTML tags from a value
        """
        # Uses regex. Regex is much faster than using an HTML parser, but will
        # strip "<2 && 3>" from a value like "1<2 && 3>2". A parser will treat
        # each cell like an HTML document, which might be overkill, but if
        # using regex breaks values then we should use a parser instead, and
        # take the knock. Assuming we won't have values with angle brackets,
        # using regex for now.
        if isinstance(value, str):
            return re.sub('<[^>]*?>', '', value)
        return value

    def trigger_export(self):
        # try:
        if self.exportable_all:
            return self._trigger_async_export()
        return self._export_file_response()
        # except Exception as e:
            # return HttpResponse(
            #     _("Export failed. Please try again later. Contact Support if issue persists."),
            #     status=500
            # )

    def validate_export_dependencies(self):
        if not hasattr(self, 'request'):
            raise NotImplementedError("TableExportMixin requires `self.request`.")
        if not hasattr(self, 'table_class'):
            raise NotImplementedError("TableExportMixin requires `self.table_class`.")

    def _trigger_async_export(self):
        """Triggers asynchronous export"""
        from corehq.apps.integration.tasks import export_all_rows_task
        export_all_rows_task.delay(
            class_path=f"{self.__class__.__module__}.{self.__class__.__name__}",
            export_context=self.get_export_context(),
        )
        return HttpResponse(_("Report is being generated. You will receive an email when it is ready."))

    # TODO Test for this
    @request_cache()
    def _export_file_response(self):
        """Returns synchronous export response"""
        file = self.export_to_file()
        return export_response(file, self.get_export_format(), self.get_export_name())

    def export_to_file(self):
        """Exports data to file object"""
        file = io.BytesIO()
        export_from_tables(self.export_table, file, self.get_export_format())
        return file

    def get_export_context(self):
        """Returns context needed to reconstruct the view for async export"""
        return {
            "domain": self.request.domain,
            "can_access_all_locations": self.request.can_access_all_locations,
            "user_id": self.request.couch_user.user_id,
            "request_params": json_request(self.request.GET),
            "config": self.config_as_dict(),
            "report_title": self.get_report_title(),
        }

    @classmethod
    def reconstruct_from_export_context(cls, context):
        """Reconstructs view instance from export context"""
        from django.test.client import RequestFactory
        from corehq.apps.users.models import CouchUser

        request = RequestFactory().get('/', data=context['request_params'])
        request.domain = context['domain']
        request.couch_user = CouchUser.get_by_user_id(context['user_id'])
        request.can_access_all_locations = context['can_access_all_locations']

        view = cls()
        view.request = request
        for config_key, config_value in context['config'].items():
            if config_key in view.EXPORT_CONFIG_KEYS:
                setattr(view, config_key, config_value)

        return view


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
class PaymentsVerificationTableView(HqHtmxActionMixin, SelectablePaginatedTableView, TableExportMixin):
    urlname = 'payments_verify_table'
    table_class = PaymentsVerifyTable
    report_title = _('Payments Verification Report')
    exportable_all = True
    export_sheet_name = 'Payments Verification Report'
    exclude_columns_in_export = ('verify_select', )

    def get_table(self, **kwargs):
        base_table = super().get_table(**kwargs)
        print("Total rows in the table", len(base_table.rows.data.data))
        base_table.user_or_cases_verification_statuses = self._get_user_or_cases_verification_status(base_table.rows.data.data)
        return base_table

    def get_table_for_export(self):
        base_table= super().get_table_for_export()
        print("Total rows in the table", len(base_table.rows.data.data))
        base_table.user_or_cases_verification_statuses = self._get_user_or_cases_verification_status(
            base_table.rows.data.data)
        return base_table


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

    # def get_context_data(self, **kwargs):
    #     context_data = super().get_context_data(**kwargs)
    #
    #     context_data['user_or_cases_verification_statuses'] = self._get_user_or_cases_verification_status(
    #         context_data['page_obj'].object_list
    #     )
    #     return context_data

    def _get_user_or_cases_verification_status(self, object_list):
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
            # case = wrap_case_search_hit(commcare_payment_case_details)
            case = commcare_payment_case_details.record.case
            if case_prop := case.get_case_property(PaymentProperties.USER_OR_CASE_ID):
                user_or_case_ids.append(case_prop)
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

    @hq_hx_action('get')
    def export(self, request, *args, **kwargs):
        return self.trigger_export()


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
