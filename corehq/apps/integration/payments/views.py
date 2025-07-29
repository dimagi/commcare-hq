import io
import re
from itertools import chain

from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.util.view_utils import request_as_dict
from couchexport.export import export_from_tables, get_writer
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.web import json_request
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from memoized import memoized

from corehq import toggles
from celery.utils.log import get_task_logger

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
from corehq.apps.users.models import HqPermissions, WebUser, CouchUser
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


class ExportableMixin:
    """Mixin to add export functionality to htmx based table views"""
    exportable_all = False  # If True, export all rows, otherwise export only the rows shown in the table.
    # Override this property to set the export format from backend.
    # Defaults to one provided in request or Format.XLS_2007
    export_format = None
    export_sheet_name = None  # Override this property to set the export sheet name. Defaults to report name.
    export_file_name = None  # Override this property to set the export file name. Defaults to report name.
    # Override this property to disable caching for the export. Applicable only when exportable_all is False.
    is_cacheable = True
    name = None  # Override this property to set the name of the export. Defaults to the class name. (Not needed ?)

    @property
    def headers(self):
        """
            Override this method to create a functional tabular report.
            Returns a DataTablesHeader() object (or a list, but preferably the former.
        """
        raise NotImplementedError

    @property
    def rows(self):
        """
            Override this method to create a functional tabular report.
            Returns 2D list of rows.
            [['row1'],[row2']]
        """
        raise NotImplementedError

    @property
    def all_rows(self):
        """
            Override this method to return all records to export
        """
        raise NotImplementedError

    @property
    def export_table(self):
        """
        Exports the report as excel.

        When rendering a complex cell, it will assign a value in the following order:
        1. cell['raw']
        2. cell['sort_key']
        3. str(cell)
        """

        def _unformat_row(row):
            def _unformat_val(val):
                if isinstance(val, dict):
                    return val.get('raw', val.get('sort_key', val))
                return self._strip_tags(val)

            return [_unformat_val(val) for val in row]

        table = [self.headers]
        rows = (_unformat_row(row) for row in self.export_rows)
        table = chain(table, rows)
        return [[self.export_sheet_name, table]]

    # TODO: Consider adding below to util
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

    @property
    def export_rows(self):
        """
        The rows that will be used in an export. Useful if you want to apply any additional
        custom formatting to mirror something that would be done in a template.
        """
        if self.exportable_all:
            return self.all_rows
        else:
            return self.rows

    def trigger_export(self):
        """
        Intention: Not to be overridden in general.
        Returns the tabular export of the data, if available.
        """
        if self.exportable_all:
            from corehq.apps.integration.tasks import export_all_rows_task
            export_all_rows_task.delay(
                class_path=f"{self.__class__.__module__}.{self.__class__.__name__}",
                export_context=self.get_export_context(),
                export_format=self.export_format,
            )
            return HttpResponse()
        else:
            return self._export_response_direct()

    @request_cache()
    def _export_response_direct(self):
        file = self.export_in_file()
        return export_response(file, self.export_format, self.name)

    def export_in_file(self):
        file = io.BytesIO()
        export_from_tables(self.export_table, file, Format.XLS_2007)
        return file

    _caching = False

    def set_export_context(self, request):
        """
        Set the export context for the view. This is used to reconstruct the view later.
        """
        self.request = request
        # TODO Check when the domain is set in the request and is it safe to use it here
        self.domain = request.domain
        self.name = self.name or self.__class__.__name__
        self.export_sheet_name = self.export_sheet_name or self.name
        self.export_file_name = self.export_file_name or self.name
        print(self.request.GET, self.request.POST)
        self.request_params = json_request(
            self.request.GET if self.request.method == 'GET' else self.request.POST
        )
        self.export_format = self.export_format or self.request_params.get('format', Format.XLS_2007)

    def get_export_context(self):
        """
        Return minimal export context required to reconstruct this export.
        """
        return {
            "domain": self.domain,
            "name": self.name,
            "user_id": self.request.couch_user.user_id,
            "request_params": self.request_params,
        }

    @classmethod
    def reconstruct_from_export_context(cls, context):
        """
        Reconstructs the report object from a minimal serialized context.
        Can be overridden by subclasses if needed.
        """
        from django.test.client import RequestFactory
        from corehq.apps.users.models import CouchUser

        request = RequestFactory().get('/', data=context['request_params'])
        request.domain = context['domain']
        request.couch_user = CouchUser.get_by_user_id(context['user_id'])

        view = cls()
        view.request = request
        view.domain = context['domain']
        view.name = context['name']
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
class PaymentsVerificationTableView(ExportableMixin, HqHtmxActionMixin, SelectablePaginatedTableView):
    urlname = 'payments_verify_table'
    table_class = PaymentsVerifyTable
    name = _('Payments Verification Report')

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

        context_data['user_or_cases_verification_statuses'] = self._get_user_or_cases_verification_status(
            context_data['page_obj'].object_list
        )
        return context_data

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
            case = wrap_case_search_hit(commcare_payment_case_details)
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
        self.set_export_context(request)
        return self.trigger_export()

    @property
    def headers(self):
        """Returns headers for table display"""
        return [column.verbose_name for column in self.table.base_columns.values()]

    @property
    @memoized
    def table(self):
        return self.table_class(data=self.get_queryset(), request=self.request)

    @property
    def rows(self):
        # TODO Maybe consider a direct approach to get rows from the table class
        """Returns paginated rows for table display"""
        return self.table.rows

    @property
    def all_rows(self):
        """Returns all rows for export without pagination"""
        queryset = self.get_queryset()
        queryset = queryset.size(queryset.count()).start(0)
        # TODO Use scrolling if the number of rows is large
        data = queryset.run().hits
        table = self.table_class(data)
        return table.rows


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



