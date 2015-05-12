from collections import namedtuple
import json
import os
import tempfile

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.http.response import Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from corehq.apps.app_manager.models import(
    Application,
    Form,
    get_apps_in_domain
)
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, View

from sqlalchemy import types

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
from corehq.apps.userreports.sql import get_indicator_table, IndicatorSqlAdapter, get_engine
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
            }
        }


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
        report = ReportConfiguration.get(report_id)
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
            'initial_columns': getattr(self.report_form, 'initial_columns', []),
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
                report_configuration = self.report_form.update_report()
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
    data_source_id = config.config_id

    report_count = ReportConfiguration.view(
        'userreports/report_configs_by_data_source',
        reduce=True,
        key=[domain, data_source_id]
    ).one()['value']

    if report_count <= 1:
        # No other reports reference this data source.
        try:
            _delete_data_source_shared(request, domain, data_source_id)
        except Http404:
            # It's possible the data source has already been deleted, but
            # that's fine with us.
            pass

    config.delete()
    messages.success(request, _(u'Report "{}" deleted!').format(config.title))
    return HttpResponseRedirect(reverse('configurable_reports_home', args=[domain]))


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def import_report(request, domain):
    if request.method == "POST":
        spec = request.POST['report_spec']
        try:
            json_spec = json.loads(spec)
            if '_id' in json_spec:
                del json_spec['_id']
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
    _delete_data_source_shared(request, domain, config_id)
    return HttpResponseRedirect(reverse('configurable_reports_home', args=[domain]))


def _delete_data_source_shared(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    adapter = IndicatorSqlAdapter(get_engine(), config)
    adapter.drop_table()
    config.delete()
    messages.success(request,
                     _(u'Data source "{}" has been deleted.'.format(config.display_name)))


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
def preview_data_source(request, domain, config_id):
    config, is_static = get_datasource_config_or_404(config_id, domain)
    table = get_indicator_table(config)

    q = Session.query(table)
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


def process_url_params(params, columns):
    format_ = params.get('format', Format.UNZIPPED_CSV)
    keyword_filters = {}
    sql_filters = []
    for key, value in params.items():
        if key == 'format':
            continue
        if not key in columns:
            raise UserQueryError('Invalid filter parameter: {}'.format(key))
        column = columns[key]

        if (
            value == 'last30'
            and isinstance(column.type, (types.Date, types.DateTime))
        ):
            sql_filters.append(column.between('2014-02-02', '2014-10-02'))
        else:
            keyword_filters[key] = value
    return ExportParameters(format_, keyword_filters, sql_filters)


@login_or_basic
@require_permission(Permissions.view_reports)
def export_data_source(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    table = get_indicator_table(config)
    q = Session.query(table)

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

    return HttpResponse('Woo! {} rows'.format(q.count()))
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as temp:
        export_from_tables([[config.table_id, get_table(q)]], temp, params.format)
        return export_response(Temp(path), params.format, config.display_name)


@login_and_domain_required
def data_source_status(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    return json_response({'isBuilt': config.meta.build.finished})


@login_and_domain_required
def choice_list_api(request, domain, report_id, filter_id):
    report = get_document_or_404(ReportConfiguration, domain, report_id)
    filter = report.get_ui_filter(filter_id)

    def get_choices(data_source, filter, search_term=None, limit=20):
        table = get_indicator_table(data_source)
        sql_column = table.c[filter.field]
        query = Session.query(sql_column)
        if search_term:
            query = query.filter(sql_column.contains(search_term))

        return [v[0] for v in query.distinct().limit(limit)]

    return json_response(get_choices(report.config, filter, request.GET.get('q', None)))


def _shared_context(domain):
    custom_data_sources = list(CustomDataSourceConfiguration.by_domain(domain))
    return {
        'domain': domain,
        'reports': ReportConfiguration.by_domain(domain),
        'data_sources': DataSourceConfiguration.by_domain(domain) + custom_data_sources,
    }
