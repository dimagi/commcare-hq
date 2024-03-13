import json
from contextlib import closing, contextmanager
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.http.response import HttpResponseServerError
from django.shortcuts import redirect, render
from django.utils.safestring import SafeText
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from django.utils.html import escape

from braces.views import JSONResponseMixin
from memoized import memoized

from couchexport.models import Format
from dimagi.utils.dates import DateSpan
from dimagi.utils.modules import to_function
from dimagi.utils.web import json_request
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context

from corehq.apps.domain.decorators import track_domain_request
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS
from corehq.apps.hqwebapp.decorators import (
    use_datatables,
    use_daterangepicker,
    use_jquery_ui,
    use_nvd3,
)
from corehq.apps.locations.permissions import conditionally_location_safe
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.dispatcher import ReportDispatcher
from corehq.apps.reports.util import DatatablesParams
from corehq.apps.reports_core.exceptions import FilterException
from corehq.apps.reports_core.filters import Choice
from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.userreports.const import (
    DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE,
    REPORT_BUILDER_EVENTS_KEY,
)
from corehq.apps.userreports.exceptions import (
    BadSpecError,
    DataSourceConfigurationNotFoundError,
    TableNotFoundWarning,
    UserReportsError,
    UserReportsFilterError,
)
from corehq.apps.userreports.models import (
    CUSTOM_REPORT_PREFIX,
    ReportConfiguration,
    StaticReportConfiguration,
    report_config_id_is_static,
)
from corehq.apps.userreports.reports.data_source import (
    ConfigurableReportDataSource,
)
from corehq.apps.userreports.reports.util import (
    ReportExport,
    report_has_location_filter,
)
from corehq.apps.userreports.tasks import export_ucr_async
from corehq.apps.userreports.util import (
    can_delete_report,
    can_edit_report,
    default_language,
    get_referring_apps,
    get_ucr_class_name,
    has_report_builder_access,
    has_report_builder_trial,
    get_report_config_or_not_found,
)
from corehq.toggles import DISABLE_COLUMN_LIMIT_IN_UCR
from corehq.util.couch import (
    DocumentNotFound,
    get_document_or_404,
)
from corehq.util.view_utils import is_ajax, reverse
from no_exceptions.exceptions import Http403


def get_filter_values(filters, request_dict, user=None):
    """
    Return a dictionary mapping filter ids to specified values
    :param filters: A list of corehq.apps.reports_core.filters.BaseFilter
        objects (or subclasses)
    :param request_dict: key word arguments from the request
    :return:
    """
    try:
        return {
            filter.css_id: filter.get_value(request_dict, user)
            for filter in filters
        }
    except FilterException as e:
        raise UserReportsFilterError(str(e))


def query_dict_to_dict(query_dict, domain, string_type_params):
    """
    Transform the given QueryDict to a normal dict where each value has been
    converted from a string to a dict (if the value is JSON). params with values 'true'
    or 'false' or numbers are casted to respective datatypes, unless the key is specified in string_type_params
    Also add the domain to the dict.

    :param query_dict: a QueryDict
    :param domain:
    :string_type_params: list of params that should not be autocasted to boolean/numbers
    :return: a dict
    """
    request_dict = json_request(query_dict)
    request_dict['domain'] = domain

    # json.loads casts strings 'true'/'false' to booleans, so undo it
    for key in string_type_params:
        if key in query_dict:
            vals = query_dict.getlist(key)
            if len(vals) > 1:
                request_dict[key] = vals
            else:
                request_dict[key] = vals[0]
    return request_dict


@contextmanager
def delete_report_config(report_config):
    yield report_config
    report_config.delete()


def _ucr_view_is_safe(view_fn, *args, **kwargs):
    return report_has_location_filter(config_id=kwargs.get('subreport_slug'),
                                      domain=kwargs.get('domain'))


@conditionally_location_safe(_ucr_view_is_safe)
class ConfigurableReportView(JSONResponseMixin, BaseDomainView):
    section_name = gettext_noop("Reports")
    template_name = 'userreports/configurable_report.html'
    slug = "configurable"
    prefix = slug
    emailable = True
    is_exportable = True
    exportable_all = True
    show_filters = True

    _domain = None

    @property
    def domain(self):
        if self._domain is not None:
            return self._domain
        return super(ConfigurableReportView, self).domain

    @use_daterangepicker
    @use_jquery_ui
    @use_datatables
    @use_nvd3
    @track_domain_request(calculated_prop='cp_n_viewed_ucr_reports')
    def dispatch(self, request, *args, **kwargs):
        if self.should_redirect_to_paywall(request):
            from corehq.apps.userreports.views import paywall_home
            return HttpResponseRedirect(paywall_home(self.domain))
        else:
            original = super(ConfigurableReportView, self).dispatch(request, *args, **kwargs)
            return original

    def should_redirect_to_paywall(self, request):
        spec = self.get_spec_or_404()
        return spec.report_meta.created_by_builder and not has_report_builder_access(request)

    @property
    def section_url(self):
        return reverse('reports_home', args=(self.domain, ))

    @property
    def is_static(self):
        return report_config_id_is_static(self.report_config_id)

    @property
    def is_custom_rendered(self):
        return self.report_config_id.startswith(CUSTOM_REPORT_PREFIX)

    @property
    @memoized
    def spec(self):
        if self.is_static:
            return StaticReportConfiguration.by_id(self.report_config_id, domain=self.domain)
        else:
            return get_report_config_or_not_found(self.domain, self.report_config_id)

    def get_spec_or_404(self):
        try:
            return self.spec
        except (DocumentNotFound, BadSpecError) as e:
            messages.error(self.request, e)
            raise Http404()

    def has_viable_configuration(self):
        try:
            self.spec
        except (DocumentNotFound, BadSpecError):
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
        report = ConfigurableReportDataSource.from_spec(self.spec, include_prefilters=True)
        report.lang = self.lang
        return report

    @property
    @memoized
    def request_dict(self):
        string_type_params = [
            filter.name
            for filter in self.filters
            if getattr(filter, 'datatype', 'string') == "string"
        ]
        query_dict = self.request.GET if self.request.method == 'GET' else self.request.POST
        return query_dict_to_dict(query_dict, self.domain, string_type_params)

    @property
    @memoized
    def request_user(self):
        try:
            return self.request.couch_user
        except AttributeError:
            return None

    @property
    @memoized
    def filter_values(self):
        return get_filter_values(self.filters, self.request_dict, user=self.request_user)

    @property
    @memoized
    def filter_context(self):
        return {
            filter.css_id: filter.context(self.request_dict, self.request_user, self.lang)
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
            elif is_ajax(request) or request.GET.get('format', None) == 'json':
                return self.get_ajax(self.request.GET)
            self.content_type = None
            try:
                self.add_warnings(self.request)
            except UserReportsError as e:
                details = ''
                if isinstance(e, DataSourceConfigurationNotFoundError):
                    error_message = DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE
                else:
                    error_message = _(
                        'It looks like there is a problem with your report. '
                        'You may need to delete and recreate the report. '
                        'If you believe you are seeing this message in error, please report an issue.'
                    )
                    details = str(e)
                self.template_name = 'userreports/report_error.html'
                allow_delete = (
                    self.report_config_id
                    and not self.is_static
                    and can_delete_report(request, self.spec)
                )

                context = {
                    'report_id': self.report_config_id,
                    'is_static': self.is_static,
                    'error_message': error_message,
                    'details': details,
                    'allow_delete': allow_delete,
                }
                context.update(self.main_context)
                return self.render_to_response(context)
            return super(ConfigurableReportView, self).get(request, *args, **kwargs)
        else:
            raise Http403()

    def post(self, request, *args, **kwargs):
        if self.has_permissions(self.domain, request.couch_user):
            self.get_spec_or_404()
            if is_ajax(request):
                return self.get_ajax(self.request.POST)
            else:
                return HttpResponseBadRequest()
        else:
            raise Http403()

    def has_permissions(self, domain, user):
        return _has_permission(domain, user, self.report_config_id)

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
            'method': 'POST',
            'headers': self.headers,
            'can_edit_report': can_edit_report(self.request, self.spec),
            'can_delete_report': can_delete_report(self.request, self.spec),
            'referring_apps': get_referring_apps(self.domain, self.report_config_id),
            'has_report_builder_trial': has_report_builder_trial(self.request),
            'report_filter_form_action_css_class': CSS_ACTION_CLASS,
        }
        context.update(self.saved_report_context_data)
        context.update(self.pop_report_builder_context_data())
        if isinstance(self.spec, ReportConfiguration) and self.spec.report_meta.builder_report_type == 'map':
            context['report_table']['default_rows'] = 100
        if self.request.couch_user.is_staff and hasattr(self.data_source, 'data_source'):
            context['queries'] = self.data_source.data_source.get_query_strings()
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
        return DataTablesHeader(*[col.data_tables_column for col in self.data_source.inner_columns])

    @classmethod
    def sanitize_page(cls, page):
        result = []
        for row in page:
            result.append({k: cls._sanitize_column(v) for (k, v) in row.items()})

        return result

    @classmethod
    def _sanitize_column(cls, col):
        if isinstance(col, str) and not isinstance(col, SafeText):
            return escape(col)
        return col

    def get_ajax(self, params):
        sort_column = params.get('iSortCol_0')
        sort_order = params.get('sSortDir_0', 'ASC')
        echo = int(params.get('sEcho', 1))
        datatables_params = DatatablesParams.from_request_dict(params)

        try:
            data_source = self.data_source
            if len(data_source.inner_columns) > 50 and not DISABLE_COLUMN_LIMIT_IN_UCR.enabled(self.domain):
                raise UserReportsError(_("This report has too many columns to be displayed"))
            data_source.set_filter_values(self.filter_values)

            if sort_column and echo != 1:
                data_source.set_order_by(
                    [(data_source.top_level_columns[int(sort_column)].column_id, sort_order.upper())]
                )

            page = list(data_source.get_data(start=datatables_params.start, limit=datatables_params.count))
            page = self.sanitize_page(page)
            total_records = data_source.get_total_records()
            total_row = data_source.get_total_row() if data_source.has_total_row else None
        except UserReportsError as e:
            if settings.DEBUG:
                raise
            return self.render_json_response({
                'error': str(e),
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
            "sEcho": params.get('sEcho', 0),
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
        from django.conf.urls import re_path as url
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

    def _get_filter_export_format(self, filter_value):
        if isinstance(filter_value, list):
            values = []
            for value in filter_value:
                if isinstance(value, Choice):
                    values.append(value.display)
                else:
                    values.append(str(value))
            return ', '.join(values)
        elif isinstance(filter_value, DateSpan):
            return filter_value.default_serialization()
        else:
            if isinstance(filter_value, Choice):
                return filter_value.display
            else:
                return str(filter_value)

    @property
    @memoized
    def report_export(self):
        return ReportExport(self.domain, self.title, self.spec, self.lang, self.filter_values)

    @property
    def export_table(self):
        return self.report_export.get_table()

    @property
    @memoized
    def email_response(self):
        with closing(BytesIO()) as temp:
            try:
                self.report_export.create_export(temp, Format.HTML)
            except UserReportsError as e:
                return self.render_json_response({'error': str(e)})
            return HttpResponse(json.dumps({
                'report': temp.getvalue().decode('utf-8'),
            }), content_type='application/json')

    @property
    @memoized
    def excel_response(self):
        file = BytesIO()
        self.report_export.create_export(file, Format.XLS_2007)
        return file

    @property
    @memoized
    def export_response(self):
        download = DownloadBase()
        res = export_ucr_async.delay(self.report_export, download.download_id, self.request.couch_user)
        download.set_task(res)
        return redirect(DownloadUCRStatusView.urlname, self.domain, download.download_id, self.report_config_id)

    @classmethod
    def sanitize_export_table(cls, table):
        result = []
        for row in table:
            result.append([cls._sanitize_column(x) for x in row])

        return result

    @classmethod
    def report_preview_data(cls, domain, report_config):
        try:
            export = ReportExport(domain, report_config.title, report_config, "en", {})
            return {
                "table": cls.sanitize_export_table(export.get_table_data()),
                "map_config": report_config.map_config,
                "chart_configs": report_config.charts,
                "aaData": cls.sanitize_page(export.get_data()),
            }
        except UserReportsError:
            # User posted an invalid report configuration
            return None
        except DataSourceConfigurationNotFoundError:
            # A temporary data source has probably expired
            # TODO: It would be more helpful just to quietly recreate the data source config from GET params
            return None


# Base class for classes that provide custom rendering for UCRs
class CustomConfigurableReport(ConfigurableReportView):
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
        except (BadSpecError, DocumentNotFound):
            raise Http404
        return report_class.as_view()(request, domain=domain, subreport_slug=report_config_id, **kwargs)

    @classmethod
    def get_report(cls, domain, slug, config_id):
        try:
            report_class = cls._report_class(domain, config_id)
        except BadSpecError:
            return None
        return report_class.get_report(domain, slug, config_id)

    @classmethod
    def url_pattern(cls):
        from django.conf.urls import re_path as url
        pattern = r'^{slug}/(?P<subreport_slug>[\w\-:]+)/$'.format(slug=cls.slug)
        return url(pattern, cls.as_view(), name=cls.slug)


@conditionally_location_safe(_ucr_view_is_safe)
class DownloadUCRStatusView(BaseDomainView):
    urlname = 'download_ucr_status'
    page_title = gettext_noop('Download UCR Status')
    section_name = gettext_noop("Reports")

    @property
    def section_url(self):
        return reverse('reports_home', args=(self.domain, ))

    def get(self, request, *args, **kwargs):
        if _has_permission(self.domain, request.couch_user, self.report_config_id):
            context = super(DownloadUCRStatusView, self).main_context
            context.update({
                'domain': self.domain,
                'download_id': kwargs['download_id'],
                'poll_url': reverse('ucr_download_job_poll',
                                    args=[self.domain, kwargs['download_id']],
                                    params={'config_id': self.report_config_id}),
                'title': _("Download Report Status"),
                'progress_text': _("Preparing report download."),
                'error_text': _("There was an unexpected error! Please try again or report an issue."),
                'next_url': reverse(ConfigurableReportView.slug, args=[self.domain, self.report_config_id]),
                'next_url_text': _("Go back to report"),
            })
            return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)
        else:
            raise Http403()

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': self.spec.title,
            'url': reverse(ConfigurableReportView.slug, args=[self.domain, self.report_config_id]),
        }]

    @property
    @memoized
    def spec(self):
        if self.is_static:
            return StaticReportConfiguration.by_id(self.report_config_id, domain=self.domain)
        else:
            return get_report_config_or_not_found(self.domain, self.report_config_id)

    @property
    def is_static(self):
        return report_config_id_is_static(self.report_config_id)

    @property
    @memoized
    def report_config_id(self):
        return self.kwargs['subreport_slug']


def _safe_download_poll(view_fn, request, domain, download_id, *args, **kwargs):
    return report_has_location_filter(request.GET.get('config_id'), domain)


@conditionally_location_safe(_safe_download_poll)
def ucr_download_job_poll(request, domain,
                          download_id,
                          template="hqwebapp/partials/shared_download_status.html"):
    config_id = request.GET.get('config_id')
    if config_id and _has_permission(domain, request.couch_user, config_id):
        try:
            context = get_download_context(download_id, 'Preparing download')
            context.update({'link_text': _('Download Report')})
        except TaskFailedError as e:
            return HttpResponseServerError(e.errors)
        return render(request, template, context)
    else:
        raise Http403()


def _has_permission(domain, user, config_id):
    if domain is None:
        return False
    if not user.is_active:
        return False
    return user.can_view_report(domain, get_ucr_class_name(config_id))
