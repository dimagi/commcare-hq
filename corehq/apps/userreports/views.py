from collections import namedtuple
import datetime
import json
import os
import tempfile

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.http.response import Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, View

from corehq.apps.app_manager.models import(
    Application,
    Form,
    get_apps_in_domain
)

from sqlalchemy import types, exc
from sqlalchemy.exc import ProgrammingError

from corehq.apps.dashboard.models import IconContext, TileConfiguration
from corehq.apps.reports.dispatcher import cls_to_view_login_and_domain
from corehq import ConfigurableReport, privileges, Session, toggles
from corehq.apps.domain.decorators import login_and_domain_required, login_or_basic
from corehq.apps.userreports.app_manager import get_case_data_source, get_form_data_source
from corehq.apps.userreports.exceptions import BadSpecError, UserQueryError
from corehq.apps.userreports.reports.builder.forms import (
    ConfigurePieChartReportForm,
    ConfigureTableReportForm,
    DataSourceForm,
    ConfigureBarChartReportForm,
    ConfigureListReportForm,
    ConfigureWorkerReportForm
)
from corehq.apps.userreports.models import (
    ReportConfiguration,
    DataSourceConfiguration,
    CustomDataSourceConfiguration,
)
from corehq.apps.userreports.sql import get_indicator_table, IndicatorSqlAdapter
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.ui.forms import (
    ConfigurableReportEditForm,
    ConfigurableDataSourceEditForm,
    ConfigurableDataSourceFromAppForm,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.util.couch import get_document_or_404

from couchexport.export import export_from_tables
from couchexport.files import Temp
from couchexport.models import Format
from couchexport.shortcuts import export_response
from django_prbac.decorators import requires_privilege_raise404

from dimagi.utils.web import json_response
from dimagi.utils.decorators.memoized import memoized


def get_datasource_config_or_404(config_id, domain):
    is_static = config_id.startswith(CustomDataSourceConfiguration._datasource_id_prefix)
    if is_static:
        config = CustomDataSourceConfiguration.by_id(config_id)
        if not config or config.domain != domain:
            raise Http404()
    else:
        config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    return config, is_static


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def configurable_reports_home(request, domain):
    return render(request, 'userreports/configurable_reports_home.html', _shared_context(domain))


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def edit_report(request, domain, report_id):
    config = get_document_or_404(ReportConfiguration, domain, report_id)
    return _edit_report_shared(request, domain, config)


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def create_report(request, domain):
    return _edit_report_shared(request, domain, ReportConfiguration(domain=domain))


class ReportBuilderView(TemplateView):

    @cls_to_view_login_and_domain
    @method_decorator(toggles.USER_CONFIGURABLE_REPORTS.required_decorator())
    @method_decorator(requires_privilege_raise404(privileges.REPORT_BUILDER))
    def dispatch(self, request, domain, **kwargs):
        self.domain = domain
        return super(ReportBuilderView, self).dispatch(request, domain, **kwargs)


class ReportBuilderTypeSelect(ReportBuilderView):
    template_name = "userreports/builder_report_type_select.html"

    def get_context_data(self, **kwargs):
        return {
            "has_apps": len(get_apps_in_domain(self.domain)) > 0,
            "domain": self.domain,
            "report": {
                "title": _("Create New Report")
            },
            "tiles": self.tiles,
        }

    @property
    def tiles(self):
        return [
            TileConfiguration(
                title=_('Chart'),
                slug='chart',
                icon='fcc fcc-piegraph-report',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'chart']),
                help_text=_('A bar graph or a pie chart to show data from your cases or forms.'
                            ' You choose the property to graph.'),
            ),
            TileConfiguration(
                title=_('Form or Case List'),
                slug='form-or-case-list',
                icon='fcc fcc-form-report',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'list']),
                help_text=_('A list of cases or form submissions.'
                            ' You choose which properties will be columns.'),
            ),
            TileConfiguration(
                title=_('Worker Report'),
                slug='worker-report',
                icon='fcc fcc-user-report',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'worker']),
                help_text=_('A table of your mobile workers.'
                            ' You choose which properties will be the columns.'),
            ),
            TileConfiguration(
                title=_('Data Table'),
                slug='data-table',
                icon='fcc fcc-datatable-report',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'table']),
                help_text=_('A table of aggregated data from form submissions or case properties.'
                            ' You choose the columns and rows.'),
            ),
        ]


class ReportBuilderDataSourceSelect(ReportBuilderView):
    template_name = 'userreports/builder_data_source_select.html'

    def dispatch(self, request, domain, report_type, **kwargs):
        self.report_type = report_type
        return super(ReportBuilderDataSourceSelect, self).dispatch(request, domain, **kwargs)

    def get_context_data(self, **kwargs):
        context = {
            "sources_map": self.form.sources_map,
            "domain": self.domain,
            'report': {"title": _("Create New Report")},
            'form': self.form,
        }
        return context

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return DataSourceForm(self.domain, self.report_type, self.request.POST)
        return DataSourceForm(self.domain, self.report_type)

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            app_source = self.form.get_selected_source()
            url_names_map = {
                'list': 'configure_list_report',
                'chart': 'configure_chart_report',
                'table': 'configure_table_report',
                'worker': 'configure_worker_report',
            }
            url_name = url_names_map[self.report_type]
            url_args = [
                (f, self.form.cleaned_data[f])
                for f in ['report_name', 'chart_type']
            ] + [
                (f, getattr(app_source, f))
                for f in ['application', 'source_type', 'source']
            ]
            return HttpResponseRedirect(
                reverse(url_name, args=[self.domain]) + '?' + '&'.join(
                    ["{}={}".format(k, v) for k, v in url_args]
                )
            )
        else:
            return self.get(request, *args, **kwargs)


class EditReportInBuilder(View):

    def dispatch(self, request, *args, **kwargs):
        report_id = kwargs['report_id']
        report = get_document_or_404(ReportConfiguration, request.domain, report_id)
        if report.report_meta.created_by_builder:
            view_class = {
                'chart': ConfigureChartReport,
                'list': ConfigureListReport,
                'worker': ConfigureWorkerReport,
                'table': ConfigureTableReport
            }[report.report_meta.builder_report_type]
            return view_class.as_view(existing_report=report)(request, *args, **kwargs)
        raise Http404("Report was not created by the report builder")


class ConfigureChartReport(ReportBuilderView):
    template_name = "userreports/partials/report_builder_configure_report.html"
    url_args = ['report_name', 'application', 'source_type', 'source']
    report_title = _("Chart Report: {}")
    existing_report = None

    def get_context_data(self, **kwargs):
        context = {
            "domain": self.domain,
            'report': {
                "title": self.report_title.format(
                    self.request.GET.get('report_name', '')
                )
            },
            'form': self.report_form,
            'property_options': self.report_form.data_source_properties.values(),
            'initial_filters': [f._asdict() for f in self.report_form.initial_filters],
            'initial_columns': [
                c._asdict() for c in getattr(self.report_form, 'initial_columns', [])
            ],
            'filter_property_help_text': _('Choose the property you would like to add as a filter to this report.'),
            'filter_display_help_text': _('Web users viewing the report will see this display text instead of the property name. Name your filter something easy for users to understand.'),
            'filter_format_help_text': _('What type of property is this filter?<br/><br/><strong>Date</strong>: select this if the property is a date.<br/><strong>Choice</strong>: select this if the property is text or multiple choice.<br/><strong>Numeric</strong>: select this if the property is a number.'),
        }
        return context

    @property
    @memoized
    def configuration_form_class(self):
        if self.existing_report:
            type_ = self.existing_report.configured_charts[0]['type']
        else:
            type_ = self.request.GET.get('chart_type')
        return {
            'multibar': ConfigureBarChartReportForm,
            'bar': ConfigureBarChartReportForm,
            'pie': ConfigurePieChartReportForm,
        }[type_]

    @property
    @memoized
    def report_form(self):
        args = [self.request.GET.get(f, '') for f in self.url_args] + [self.existing_report]
        if self.request.method == 'POST':
            args.append(self.request.POST)
        return self.configuration_form_class(*args)

    def post(self, *args, **kwargs):
        if self.report_form.is_valid():
            if self.report_form.existing_report:
                try:
                    report_configuration = self.report_form.update_report()
                except ValidationError as e:
                    messages.error(self.request, e.message)
                    return self.get(*args, **kwargs)
            else:
                report_configuration = self.report_form.create_report()
            return HttpResponseRedirect(
                reverse(ConfigurableReport.slug, args=[self.domain, report_configuration._id])
            )
        return self.get(*args, **kwargs)


class ConfigureListReport(ConfigureChartReport):
    report_title = _("List Report: {}")

    @property
    @memoized
    def configuration_form_class(self):
        return ConfigureListReportForm


class ConfigureTableReport(ConfigureChartReport):
    report_title = _("Table Report: {}")

    @property
    @memoized
    def configuration_form_class(self):
        return ConfigureTableReportForm


class ConfigureWorkerReport(ConfigureChartReport):
    report_title = _("Worker Report: {}")

    @property
    @memoized
    def configuration_form_class(self):
        return ConfigureWorkerReportForm


def _edit_report_shared(request, domain, config):
    if request.method == 'POST':
        form = ConfigurableReportEditForm(domain, config, data=request.POST)
        if form.is_valid():
            form.save(commit=True)
            messages.success(request, _(u'Report "{}" saved!').format(config.title))
            return HttpResponseRedirect(reverse('edit_configurable_report', args=[domain, config._id]))
    else:
        form = ConfigurableReportEditForm(domain, config)
    context = _shared_context(domain)
    context.update({
        'form': form,
        'report': config
    })
    return render(request, "userreports/edit_report_config.html", context)


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def delete_report(request, domain, report_id):
    config = get_document_or_404(ReportConfiguration, domain, report_id)

    # Delete the data source too if it's not being used by any other reports.
    data_source, __ = get_datasource_config_or_404(config.config_id, domain)
    if data_source.get_report_count() <= 1:
        # No other reports reference this data source.
        try:
            delete_data_source_shared(domain, data_source._id, request)
        except Http404:
            # It's possible the data source has already been deleted, but
            # that's fine with us.
            pass

    config.delete()
    messages.success(request, _(u'Report "{}" deleted!').format(config.title))
    redirect = request.GET.get("redirect", None)
    if not redirect:
        redirect = reverse('configurable_reports_home', args=[domain])
    return HttpResponseRedirect(redirect)


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def import_report(request, domain):
    if request.method == "POST":
        spec = request.POST['report_spec']
        try:
            json_spec = json.loads(spec)
            if '_id' in json_spec:
                del json_spec['_id']
            json_spec['domain'] = domain
            report = ReportConfiguration.wrap(json_spec)
            report.validate()
            report.save()
            messages.success(request, _('Report created!'))
            return HttpResponseRedirect(reverse('edit_configurable_report', args=[domain, report._id]))
        except (ValueError, BadSpecError) as e:
            messages.error(request, _('Bad report source: {}').format(e))
    else:
        spec = _('paste report source here')
    context = _shared_context(domain)
    context['spec'] = spec
    return render(request, "userreports/import_report.html", context)


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def report_source_json(request, domain, report_id):
    config = get_document_or_404(ReportConfiguration, domain, report_id)
    del config._doc['_rev']
    return json_response(config)


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def edit_data_source(request, domain, config_id):
    config, is_static = get_datasource_config_or_404(config_id, domain)
    return _edit_data_source_shared(request, domain, config, read_only=is_static)


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def create_data_source(request, domain):
    return _edit_data_source_shared(request, domain, DataSourceConfiguration(domain=domain))


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def create_data_source_from_app(request, domain):
    if request.method == 'POST':
        form = ConfigurableDataSourceFromAppForm(domain, request.POST)
        if form.is_valid():
            # save config
            app_source = form.app_source_helper.get_app_source(form.cleaned_data)
            app = Application.get(app_source.application)
            if app_source.source_type == 'case':
                data_source = get_case_data_source(app, app_source.source)
                data_source.save()
                messages.success(request, _(u"Data source created for '{}'".format(app_source.source)))
            else:
                assert app_source.source_type == 'form'
                xform = Form.get_form(app_source.source)
                data_source = get_form_data_source(app, xform)
                data_source.save()
                messages.success(request, _(u"Data source created for '{}'".format(xform.default_name())))

            return HttpResponseRedirect(reverse('edit_configurable_data_source', args=[domain, data_source._id]))
    else:
        form = ConfigurableDataSourceFromAppForm(domain)
    context = _shared_context(domain)
    context['sources_map'] = form.app_source_helper.all_sources
    context['form'] = form
    return render(request, 'userreports/data_source_from_app.html', context)


def _edit_data_source_shared(request, domain, config, read_only=False):
    if request.method == 'POST':
        form = ConfigurableDataSourceEditForm(domain, config, read_only, data=request.POST)
        if form.is_valid():

            config = form.save(commit=True)
            messages.success(request, _(u'Data source "{}" saved!').format(config.display_name))

    else:
        form = ConfigurableDataSourceEditForm(domain, config, read_only)
    context = _shared_context(domain)
    context.update({
        'form': form,
        'data_source': config,
        'read_only': read_only
    })
    return render(request, "userreports/edit_data_source.html", context)


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
@require_POST
def delete_data_source(request, domain, config_id):
    delete_data_source_shared(domain, config_id, request)
    return HttpResponseRedirect(reverse('configurable_reports_home', args=[domain]))


def delete_data_source_shared(domain, config_id, request=None):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    adapter = IndicatorSqlAdapter(config)
    adapter.drop_table()
    config.delete()
    if request:
        messages.success(
            request,
            _(u'Data source "{}" has been deleted.'.format(config.display_name))
        )


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
@require_POST
def rebuild_data_source(request, domain, config_id):
    config, is_static = get_datasource_config_or_404(config_id, domain)
    messages.success(
        request,
        _('Table "{}" is now being rebuilt. Data should start showing up soon').format(
            config.display_name
        )
    )

    rebuild_indicators.delay(config_id)
    return HttpResponseRedirect(reverse('edit_configurable_data_source', args=[domain, config._id]))


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def data_source_json(request, domain, config_id):
    config, _ = get_datasource_config_or_404(config_id, domain)
    del config._doc['_rev']
    return json_response(config)


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def preview_data_source(request, domain, config_id):
    config, is_static = get_datasource_config_or_404(config_id, domain)
    adapter = IndicatorSqlAdapter(config)
    q = adapter.get_query_object()
    context = _shared_context(domain)
    context.update({
        'data_source': config,
        'columns': q.column_descriptions,
        'data': q[:20],
        'total_rows': q.count(),
    })
    return render(request, "userreports/preview_data.html", context)


ExportParameters = namedtuple('ExportParameters',
                              ['format', 'keyword_filters', 'sql_filters'])


def _last_n_days(column, value):
    if not isinstance(column.type, (types.Date, types.DateTime)):
        raise UserQueryError(_("You can only use 'lastndays' on date columns"))
    end = datetime.date.today()
    start = end - datetime.timedelta(days=int(value))
    return column.between(start, end)


def _range_filter(column, value):
    try:
        start, end = value.split('..')
    except ValueError:
        raise UserQueryError(_('Ranges must have the format "start..end"'))
    return column.between(start, end)


sql_directives = [
    # (suffix matching url parameter, callable returning a filter),
    ('-lastndays', _last_n_days),
    ('-range', _range_filter),
]


def process_url_params(params, columns):
    """
    Converts a dictionary of parameters from the user to sql filters.

    If a parameter is of the form <field name>-<suffix>, where suffix is
    defined in `sql_directives`, the corresponding function is used to
    produce a filter.
    """
    # support passing `format` instead of `$format` so we don't break people's
    # existing URLs.  Let's remove this once we can.
    format_ = params.get('$format', params.get('format', Format.UNZIPPED_CSV))
    keyword_filters = {}
    sql_filters = []
    for key, value in params.items():
        if key in ('$format', 'format'):
            continue

        for suffix, fn in sql_directives:
            if key.endswith(suffix):
                field = key[:-len(suffix)]
                if field not in columns:
                    raise UserQueryError(_('No field named {}').format(field))
                sql_filters.append(fn(columns[field], value))
                break
        else:
            if key in columns:
                keyword_filters[key] = value
            else:
                raise UserQueryError(_('Invalid filter parameter: {}')
                                     .format(key))
    return ExportParameters(format_, keyword_filters, sql_filters)


@login_or_basic
@require_permission(Permissions.view_reports)
def export_data_source(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    adapter = IndicatorSqlAdapter(config)
    q = adapter.get_query_object()
    table = adapter.get_table()

    try:
        params = process_url_params(request.GET, table.columns)
    except UserQueryError as e:
        return HttpResponse(e.message, status=400)

    q = q.filter_by(**params.keyword_filters)
    for sql_filter in params.sql_filters:
        q = q.filter(sql_filter)

    # build export
    def get_table(q):
        yield table.columns.keys()
        for row in q:
            yield row

    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as tmpfile:
        try:
            tables = [[config.table_id, get_table(q)]]
            export_from_tables(tables, tmpfile, params.format)
        except exc.DataError:
            msg = _("There was a problem executing your query, please make "
                    "sure your parameters are valid.")
            return HttpResponse(msg, status=400)
        return export_response(Temp(path), params.format, config.display_name)


@login_and_domain_required
def data_source_status(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    return json_response({'isBuilt': config.meta.build.finished})


@login_and_domain_required
def choice_list_api(request, domain, report_id, filter_id):
    report = get_document_or_404(ReportConfiguration, domain, report_id)
    filter = report.get_ui_filter(filter_id)

    def get_choices(data_source, filter, search_term=None, limit=20, page=0):
        table = get_indicator_table(data_source)
        sql_column = table.c[filter.field]
        query = Session.query(sql_column)
        if search_term:
            query = query.filter(sql_column.contains(search_term))

        offset = page * limit
        try:
            return [v[0] for v in query.distinct().order_by(sql_column).limit(limit).offset(offset)]
        except ProgrammingError:
            return []

    return json_response(get_choices(
        report.config,
        filter,
        request.GET.get('q', None),
        limit=int(request.GET.get('limit', 20)),
        page=int(request.GET.get('page', 1)) - 1
    ))


def _shared_context(domain):
    custom_data_sources = list(CustomDataSourceConfiguration.by_domain(domain))
    return {
        'domain': domain,
        'reports': ReportConfiguration.by_domain(domain),
        'data_sources': DataSourceConfiguration.by_domain(domain) + custom_data_sources,
    }
