import json
import os
import tempfile
from StringIO import StringIO
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.reports.util import \
    DEFAULT_CSS_FORM_ACTIONS_CLASS_REPORT_FILTER
from corehq.apps.style.decorators import (
    use_select2,
    use_daterangepicker,
    use_jquery_ui,
    use_nvd3,
    use_datatables,
)
from corehq.apps.userreports.const import REPORT_BUILDER_EVENTS_KEY
from couchexport.shortcuts import export_response
from dimagi.utils.modules import to_function
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.utils.translation import ugettext as _, ugettext_noop
from braces.views import JSONResponseMixin
from corehq.apps.reports.dispatcher import (
    ReportDispatcher,
)
from corehq.apps.reports.models import ReportConfig
from corehq.apps.reports_core.exceptions import FilterException
from corehq.apps.userreports.exceptions import (
    BadSpecError,
    UserReportsError,
    TableNotFoundWarning,
    UserReportsFilterError,
    DataSourceConfigurationNotFoundError)
from corehq.apps.userreports.models import (
    STATIC_PREFIX,
    CUSTOM_REPORT_PREFIX,
    StaticReportConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.reports.util import (
    get_expanded_columns,
)
from corehq.apps.userreports.util import (
    default_language,
    has_report_builder_trial,
    can_edit_report,
)
from corehq.util.couch import get_document_or_404, get_document_or_not_found, \
    DocumentNotFound
from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.couch.pagination import DatatablesParams
from dimagi.utils.decorators.memoized import memoized

from dimagi.utils.web import json_request
from no_exceptions.exceptions import Http403

from corehq.apps.reports.datatables import DataTablesHeader


UCR_EXPORT_TO_EXCEL_ROW_LIMIT = 1000


class ConfigurableReport(JSONResponseMixin, BaseDomainView):
    section_name = ugettext_noop("Reports")
    template_name = 'userreports/configurable_report.html'
    slug = "configurable"
    prefix = slug
    emailable = True
    is_exportable = True
    show_filters = True

    _domain = None

    @property
    def domain(self):
        if self._domain is not None:
            return self._domain
        return super(ConfigurableReport, self).domain

    @use_select2
    @use_daterangepicker
    @use_jquery_ui
    @use_datatables
    @use_nvd3
    def dispatch(self, request, *args, **kwargs):
        original = super(ConfigurableReport, self).dispatch(request, *args, **kwargs)
        return original

    @property
    def section_url(self):
        # todo what should the parent section url be?
        return "#"

    @property
    def is_static(self):
        return any(
            self.report_config_id.startswith(prefix)
            for prefix in [STATIC_PREFIX, CUSTOM_REPORT_PREFIX]
        )

    @property
    def is_custom_rendered(self):
        return self.report_config_id.startswith(CUSTOM_REPORT_PREFIX)

    @property
    @memoized
    def spec(self):
        if self.is_static:
            return StaticReportConfiguration.by_id(self.report_config_id)
        else:
            return get_document_or_not_found(ReportConfiguration, self.domain, self.report_config_id)

    def get_spec_or_404(self):
        try:
            return self.spec
        except DocumentNotFound:
            raise Http404()

    def has_viable_configuration(self):
        try:
            self.spec
        except DocumentNotFound:
            return False
        else:
            return True

    @property
    def title(self):
        return self.spec.title

    @property
    def page_name(self):
        return self.spec.title

    @property
    @memoized
    def data_source(self):
        report = ReportFactory.from_spec(self.spec)
        report.lang = self.lang
        return report

    @property
    @memoized
    def request_dict(self):
        request_dict = json_request(self.request.GET)
        request_dict['domain'] = self.domain
        return request_dict

    @property
    @memoized
    def filter_values(self):
        try:
            return {
                filter.css_id: filter.get_value(self.request_dict)
                for filter in self.filters
            }
        except FilterException, e:
            raise UserReportsFilterError(unicode(e))

    @property
    @memoized
    def filter_context(self):
        return {
            filter.css_id: filter.context(self.filter_values[filter.css_id], self.lang)
            for filter in self.filters
        }

    @property
    @memoized
    def filters(self):
        return self.spec.ui_filters

    _report_config_id = None

    @property
    def report_config_id(self):
        if self._report_config_id is not None:
            return self._report_config_id
        return self.kwargs['subreport_slug']

    _lang = None

    @property
    def lang(self):
        if self._lang is not None:
            return self._lang
        return self.request.couch_user.language or default_language()

    def get(self, request, *args, **kwargs):
        if self.has_permissions(self.domain, request.couch_user):
            self.get_spec_or_404()
            if kwargs.get('render_as') == 'email':
                return self.email_response
            elif kwargs.get('render_as') == 'excel':
                return self.excel_response
            elif request.GET.get('format', None) == "export":
                return self.export_response
            elif request.GET.get('format', None) == 'export_size_check':
                return self.export_size_check_response
            elif request.is_ajax() or request.GET.get('format', None) == 'json':
                return self.get_ajax(self.request)
            self.content_type = None
            try:
                self.add_warnings(self.request)
            except UserReportsError as e:
                details = ''
                if isinstance(e, DataSourceConfigurationNotFoundError):
                    error_message = _(
                        'Sorry! There was a problem viewing your report. '
                        'This likely occurred because the application associated with the report was deleted. '
                        'In order to view this data using the Report Builder you will have to delete this report '
                        'and then build it again. Click below to delete it.'
                    )
                else:
                    error_message = _(
                        'It looks like there is a problem with your report. '
                        'You may need to delete and recreate the report. '
                        'If you believe you are seeing this message in error, please report an issue.'
                    )
                    details = unicode(e)
                self.template_name = 'userreports/report_error.html'
                context = {
                    'report_id': self.report_config_id,
                    'is_static': self.is_static,
                    'error_message': error_message,
                    'details': details,
                }
                context.update(self.main_context)
                return self.render_to_response(context)
            return super(ConfigurableReport, self).get(request, *args, **kwargs)
        else:
            raise Http403()

    def has_permissions(self, domain, user):
        return True

    def add_warnings(self, request):
        for warning in self.data_source.column_warnings:
            messages.warning(request, warning)

    @property
    def page_context(self):
        context = {
            'report': self,
            'report_table': {'default_rows': 25},
            'filter_context': self.filter_context,
            'url': self.url,
            'headers': self.headers,
            'can_edit_report': can_edit_report(self.request, self),
            'has_report_builder_trial': has_report_builder_trial(self.request),
            'report_filter_form_action_css_class': DEFAULT_CSS_FORM_ACTIONS_CLASS_REPORT_FILTER,
        }
        context.update(self.saved_report_context_data)
        context.update(self.pop_report_builder_context_data())
        return context

    def pop_report_builder_context_data(self):
        """
        Pop any report builder data stored on the session and return a dict to
        be included in the template context.
        """
        return {
            'report_builder_events': self.request.session.pop(REPORT_BUILDER_EVENTS_KEY, [])
        }

    @property
    def saved_report_context_data(self):
        def _get_context_for_saved_report(report_config):
            if report_config:
                report_config_data = report_config.to_json()
                report_config_data['filters'].update(report_config.get_date_range())
                return report_config_data
            else:
                return ReportConfig.default()

        saved_report_config_id = self.request.GET.get('config_id')
        saved_report_config = get_document_or_404(ReportConfig, self.domain, saved_report_config_id) \
            if saved_report_config_id else None

        return {
            'report_configs': [
                _get_context_for_saved_report(saved_report)
                for saved_report in ReportConfig.by_domain_and_owner(
                    self.domain, self.request.couch_user._id, report_slug=self.slug
                )
            ],
            'default_config': _get_context_for_saved_report(saved_report_config),
            'datespan_filters': ReportConfig.datespan_filter_choices(self.datespan_filters, self.lang),
        }

    @property
    def has_datespan(self):
        return bool(self.datespan_filters)

    @property
    def datespan_filters(self):
        return [
            f for f in self.spec.filters
            if f['type'] == 'date'
        ]

    @property
    def headers(self):
        return DataTablesHeader(*[col.data_tables_column for col in self.data_source.columns])

    def get_ajax(self, request):
        try:
            data_source = self.data_source
            if len(data_source.columns) > 50:
                raise UserReportsError(_("This report has too many columns to be displayed"))
            data_source.set_filter_values(self.filter_values)

            sort_column = request.GET.get('iSortCol_0')
            sort_order = request.GET.get('sSortDir_0', 'ASC')
            echo = int(request.GET.get('sEcho', 1))
            if sort_column and echo != 1:
                data_source.set_order_by(
                    [(data_source.column_configs[int(sort_column)].column_id, sort_order.upper())]
                )

            datatables_params = DatatablesParams.from_request_dict(request.GET)
            page = list(data_source.get_data(start=datatables_params.start, limit=datatables_params.count))

            total_records = data_source.get_total_records()
            total_row = data_source.get_total_row() if data_source.has_total_row else None
        except UserReportsError as e:
            if settings.DEBUG:
                raise
            return self.render_json_response({
                'error': e.message,
                'aaData': [],
                'iTotalRecords': 0,
                'iTotalDisplayRecords': 0,
            })
        except TableNotFoundWarning:
            if self.spec.report_meta.created_by_builder:
                msg = _(
                    "The database table backing your report does not exist yet. "
                    "Please wait while the report is populated."
                )
            else:
                msg = _(
                    "The database table backing your report does not exist yet. "
                    "You must rebuild the data source before viewing the report."
                )
            return self.render_json_response({
                'warning': msg
            })

        json_response = {
            'aaData': page,
            "sEcho": self.request_dict.get('sEcho', 0),
            "iTotalRecords": total_records,
            "iTotalDisplayRecords": total_records,
        }
        if total_row is not None:
            json_response["total_row"] = total_row
        return self.render_json_response(json_response)

    def _get_initial(self, request, **kwargs):
        pass

    @classmethod
    def url_pattern(cls):
        from django.conf.urls import url
        pattern = r'^{slug}/(?P<subreport_slug>[\w\-:]+)/$'.format(slug=cls.slug)
        return url(pattern, cls.as_view(), name=cls.slug)

    @property
    def type(self):
        """
        Used to populate ReportConfig.report_type
        """
        return self.prefix

    @property
    def sub_slug(self):
        """
        Used to populate ReportConfig.subreport_slug
        """
        return self.report_config_id

    @classmethod
    def get_report(cls, domain, slug, report_config_id):
        report = cls()
        report._domain = domain
        report._report_config_id = report_config_id
        if not report.has_viable_configuration():
            return None
        report.name = report.title
        return report

    @property
    def url(self):
        return reverse(self.slug, args=[self.domain, self.report_config_id])

    @property
    @memoized
    def export_table(self):
        try:
            data = self.data_source
            data.set_filter_values(self.filter_values)
            data.set_order_by([(o['field'], o['order']) for o in self.spec.sort_expression])
        except UserReportsError as e:
            return self.render_json_response({
                'error': e.message,
            })

        raw_rows = list(data.get_data())
        headers = [column.header for column in self.data_source.columns]

        column_id_to_expanded_column_ids = get_expanded_columns(data.column_configs, data.config)
        column_ids = []
        for column in self.spec.report_columns:
            column_ids.extend(column_id_to_expanded_column_ids.get(column.column_id, [column.column_id]))

        rows = [[raw_row[column_id] for column_id in column_ids] for raw_row in raw_rows]
        total_rows = [data.get_total_row()] if data.has_total_row else []
        return [
            [
                self.title,
                [headers] + rows + total_rows
            ]
        ]

    @property
    @memoized
    def email_response(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as temp:
            export_from_tables(self.export_table, temp, Format.HTML)
        with open(path) as f:
            return HttpResponse(json.dumps({
                'report': f.read(),
            }))

    @property
    @memoized
    def excel_response(self):
        file = StringIO()
        export_from_tables(self.export_table, file, Format.XLS_2007)
        return file

    @property
    @memoized
    def export_too_large(self):
        data = self.data_source
        data.set_filter_values(self.filter_values)
        total_rows = data.get_total_records()
        return total_rows > UCR_EXPORT_TO_EXCEL_ROW_LIMIT

    @property
    @memoized
    def export_size_check_response(self):
        try:
            too_large = self.export_too_large
        except UserReportsError as e:
            if settings.DEBUG:
                raise
            return self.render_json_response({
                'export_allowed': False,
                'message': e.message,
            })

        if too_large:
            return self.render_json_response({
                'export_allowed': False,
                'message': _(
                    "Report export is limited to {number} rows. "
                    "Please filter the data in your report to "
                    "{number} or fewer rows before exporting"
                ).format(number=UCR_EXPORT_TO_EXCEL_ROW_LIMIT),
            })
        return self.render_json_response({
            "export_allowed": True,
        })

    @property
    @memoized
    def export_response(self):
        if self.export_too_large:
            # Frontend should check size with export_size_check_response()
            # Before hitting this endpoint, but we check the size again here
            # in case the user modifies the url manually.
            return HttpResponseBadRequest()

        temp = StringIO()
        export_from_tables(self.export_table, temp, Format.XLS_2007)
        return export_response(temp, Format.XLS_2007, self.title)


# Base class for classes that provide custom rendering for UCRs
class CustomConfigurableReport(ConfigurableReport):
    # Ensures that links in saved reports will hit CustomConfigurableReportDispatcher
    slug = 'custom_configurable'


class CustomConfigurableReportDispatcher(ReportDispatcher):
    slug = prefix = 'custom_configurable'
    map_name = 'CUSTOM_UCR'

    @staticmethod
    def _report_class(domain, config_id):
        class_path = StaticReportConfiguration.report_class_by_domain_and_id(
            domain, config_id
        )
        return to_function(class_path)

    def dispatch(self, request, domain, subreport_slug, **kwargs):
        report_config_id = subreport_slug
        try:
            report_class = self._report_class(domain, report_config_id)
        except BadSpecError:
            raise Http404
        return report_class.as_view()(request, domain=domain, subreport_slug=report_config_id, **kwargs)

    def get_report(self, domain, slug, config_id):
        try:
            report_class = self._report_class(domain, config_id)
        except BadSpecError:
            return None
        return report_class.get_report(domain, slug, config_id)

    @classmethod
    def url_pattern(cls):
        from django.conf.urls import url
        pattern = r'^{slug}/(?P<subreport_slug>[\w\-:]+)/$'.format(slug=cls.slug)
        return url(pattern, cls.as_view(), name=cls.slug)
