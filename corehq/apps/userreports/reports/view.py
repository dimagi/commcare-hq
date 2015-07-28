import json
import os
import tempfile
from StringIO import StringIO
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404
from django.utils.translation import ugettext_noop as _
from django.views.generic.base import TemplateView
from braces.views import JSONResponseMixin
from corehq.apps.reports.dispatcher import cls_to_view_login_and_domain
from corehq.apps.reports.models import ReportConfig
from corehq.apps.reports_core.exceptions import FilterException
from corehq.apps.userreports.exceptions import (
    UserReportsError, TableNotFoundWarning,
    UserReportsFilterError)
from corehq.apps.userreports.models import ReportConfiguration, CUSTOM_PREFIX, CustomReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.util.couch import get_document_or_404, get_document_or_not_found, \
    DocumentNotFound
from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.couch.pagination import DatatablesParams
from dimagi.utils.decorators.memoized import memoized

from dimagi.utils.web import json_request
from no_exceptions.exceptions import Http403

from corehq.apps.reports.datatables import DataTablesHeader


class ConfigurableReport(JSONResponseMixin, TemplateView):
    template_name = 'userreports/configurable_report.html'
    slug = "configurable"
    prefix = slug
    emailable = True

    @property
    def is_custom(self):
        return self.report_config_id.startswith(CUSTOM_PREFIX)

    @property
    @memoized
    def spec(self):
        if self.is_custom:
            return CustomReportConfiguration.by_id(self.report_config_id)
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

    @cls_to_view_login_and_domain
    def dispatch(self, request, report_config_id, **kwargs):
        self.request = request
        self.domain = request.domain
        self.report_config_id = report_config_id
        self.lang = self.request.couch_user.language
        user = request.couch_user
        if self.has_permissions(self.domain, user):
            self.get_spec_or_404()
            if kwargs.get('render_as') == 'email':
                return self.email_response
            elif kwargs.get('render_as') == 'excel':
                return self.excel_response
            elif request.is_ajax() or request.GET.get('format', None) == 'json':
                return self.get_ajax(request, **kwargs)
            self.content_type = None
            self.add_warnings(request)
            return super(ConfigurableReport, self).dispatch(request, self.domain, **kwargs)
        else:
            raise Http403()

    def has_permissions(self, domain, user):
        return True

    def add_warnings(self, request):
        for warning in self.data_source.column_warnings:
            messages.warning(request, warning)

    def get_context_data(self, **kwargs):
        context = {
            'domain': self.domain,
            'report': self,
            'filter_context': self.filter_context,
            'url': self.url,
            'headers': self.headers
        }
        context.update(self.saved_report_context_data)
        return context

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
            'datespan_filters': [{
                'display': _('Choose a date filter...'),
                'slug': None,
            }] + self.datespan_filters,
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

    def get_ajax(self, request, domain=None, **kwargs):
        try:
            data = self.data_source
            data.set_filter_values(self.filter_values)
            data.set_order_by([(o['field'], o['order']) for o in self.spec.sort_expression])
            total_records = data.get_total_records()
        except UserReportsError as e:
            if settings.DEBUG:
                raise
            return self.render_json_response({
                'error': e.message,
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

        # todo: this is ghetto pagination - still doing a lot of work in the database
        datatables_params = DatatablesParams.from_request_dict(request.GET)
        end = min(datatables_params.start + datatables_params.count, total_records)
        page = list(data.get_data())[datatables_params.start:end]
        return self.render_json_response({
            'aaData': page,
            "sEcho": self.request_dict.get('sEcho', 0),
            "iTotalRecords": total_records,
            "iTotalDisplayRecords": total_records,
        })

    def _get_initial(self, request, **kwargs):
        pass

    @classmethod
    def url_pattern(cls):
        from django.conf.urls import url
        pattern = r'^{slug}/(?P<report_config_id>[\w\-:]+)/$'.format(slug=cls.slug)
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
        report.domain = domain
        report.report_config_id = report_config_id
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

        report_config = ReportConfiguration.get(self.report_config_id)
        raw_rows = list(data.get_data())
        headers = [column.header for column in self.data_source.columns]
        columns = [column.column_id for column in report_config.report_columns]
        rows = [[raw_row[column] for column in columns] for raw_row in raw_rows]
        return [
            [
                self.title,
                [headers] + rows
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
