import json
import os
import tempfile
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.http.response import Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from dimagi.utils.decorators.memoized import memoized
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from corehq.apps.reports.dispatcher import cls_to_view_login_and_domain
from corehq.apps.app_manager.models import get_apps_in_domain
from corehq import Session, ConfigurableReport
from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.userreports.app_manager import get_case_data_source, get_form_data_source
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.builder.forms import (
    ConfigureNewBarChartReport,
    ConfigureNewPieChartReport,
    ConfigureNewTableReport,
    CreateNewReportForm,
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
    ConfigurableFormDataSourceFromAppForm)
from corehq.util.couch import get_document_or_404
from couchexport.export import export_from_tables
from couchexport.files import Temp
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.web import json_response


def get_datasource_config_or_404(config_id, domain):
    is_static = config_id.startswith(CustomDataSourceConfiguration._datasource_id_prefix)
    if is_static:
        config = CustomDataSourceConfiguration.by_id(config_id)
        if not config or config.domain != domain:
            raise Http404()
    else:
        config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    return config, is_static


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def configurable_reports_home(request, domain):
    return render(request, 'userreports/configurable_reports_home.html', _shared_context(domain))


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def edit_report(request, domain, report_id):
    config = get_document_or_404(ReportConfiguration, domain, report_id)
    return _edit_report_shared(request, domain, config)


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def create_report(request, domain):
    return _edit_report_shared(request, domain, ReportConfiguration(domain=domain))


class ReportBuilderView(TemplateView):
    @cls_to_view_login_and_domain
    @method_decorator(toggles.USER_CONFIGURABLE_REPORTS.required_decorator())
    def dispatch(self, request, domain, **kwargs):
        self.domain = domain
        return super(ReportBuilderView, self).dispatch(request, domain, **kwargs)


class CreateNewReportBuilderView(ReportBuilderView):
    template_name = "userreports/create_new_report_builder.html"

    def get_context_data(self, **kwargs):
        apps = get_apps_in_domain(self.domain, full=True, include_remote=False)
        context = {
            "sources_map": {
                app._id: {
                    "case": [{"text": t, "value": t} for t in app.get_case_types()],
                    "form": [
                        {
                            "text": form.default_name(),
                            "value": form.get_unique_id()
                        } for form in app.get_forms()
                    ]
                } for app in apps
            },
            "domain": self.domain,
            'report': {
                "title": _("Create New Report"),
            },
            'form': self.create_new_report_builder_form,
        }
        return context

    @property
    @memoized
    def create_new_report_builder_form(self):
        if self.request.method == 'POST':
            return CreateNewReportForm(self.domain, self.request.POST)
        return CreateNewReportForm(self.domain)

    def post(self, request, *args, **kwargs):
        if self.create_new_report_builder_form.is_valid():
            report_type = self.create_new_report_builder_form.cleaned_data['report_type']
            url_names_map = {
                'bar_chart': 'configure_bar_chart_report_builder',
                'pie_chart': 'configure_pie_chart_report_builder',
                'table': 'configure_table_report_builder',
            }
            url_name = url_names_map[report_type]
            return HttpResponseRedirect(
                reverse(url_name, args=[self.domain]) + '?' + '&'.join([
                    '%(key)s=%(value)s' % {
                        'key': field,
                        'value': escape(self.create_new_report_builder_form.cleaned_data[field]),
                    } for field in [
                        'application',
                        'source_type',
                        'report_source',
                    ]
                ])
            )
        else:
            return self.get(request, *args, **kwargs)


class ConfigureBarChartReportBuilderView(ReportBuilderView):
    template_name = "userreports/partials/report_builder_configure_report.html"
    configure_report_form_class = ConfigureNewBarChartReport
    report_title = _("Create New Report > Configure Bar Chart Report")

    def get_context_data(self, **kwargs):
        context = {
            "domain": self.domain,
            'report': {"title": self.report_title},
            'form': self.report_form,
            'property_options': self.report_form.data_source_properties.values()
        }
        return context

    @property
    @memoized
    def report_form(self):
        app_id = self.request.GET.get('application', '')
        source_type = self.request.GET.get('source_type', '')
        report_source = self.request.GET.get('report_source', '')
        args = [app_id, source_type, report_source]
        if self.request.method == 'POST':
            args.append(self.request.POST)
        return self.configure_report_form_class(*args)

    def post(self, *args, **kwargs):
        if self.report_form.is_valid():
            report_configuration = self.report_form.create_report()
            return HttpResponseRedirect(
                reverse(
                    ConfigurableReport.slug,
                    args=[self.domain, report_configuration._id]
                )
            )
        return self.get(*args, **kwargs)


class ConfigurePieChartReportBuilderView(ConfigureBarChartReportBuilderView):
    configure_report_form_class = ConfigureNewPieChartReport
    report_title = _("Create New Report > Configure Pie Chart Report")


class ConfigureTableReportBuilderView(ConfigureBarChartReportBuilderView):
    # Temporarily building this view off of ConfigureBarChartReportBuilderView.
    # We'll probably want to inherit from a common ancestor in the end?
    configure_report_form_class = ConfigureNewTableReport
    report_title = _("Create New Report > Configure Table Report")


def _edit_report_shared(request, domain, config):
    if request.method == 'POST':
        form = ConfigurableReportEditForm(domain, config, request.POST)
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
@require_POST
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


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def report_source_json(request, domain, report_id):
    config = get_document_or_404(ReportConfiguration, domain, report_id)
    del config._doc['_rev']
    return json_response(config)


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def edit_data_source(request, domain, config_id):
    config, is_static = get_datasource_config_or_404(config_id, domain)
    return _edit_data_source_shared(request, domain, config, read_only=is_static)


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def create_data_source(request, domain):
    return _edit_data_source_shared(request, domain, DataSourceConfiguration(domain=domain))


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def create_data_source_from_app(request, domain):
    if request.method == 'POST':
        form = ConfigurableDataSourceFromAppForm(domain, request.POST)
        if form.is_valid():
            # save config
            data_source = get_case_data_source(form.app, form.cleaned_data['case_type'])
            data_source.save()
            messages.success(request, _(u"Data source created for '{}'".format(form.cleaned_data['case_type'])))
            return HttpResponseRedirect(reverse('edit_configurable_data_source', args=[domain, data_source._id]))
    else:
        form = ConfigurableDataSourceFromAppForm(domain)
    context = _shared_context(domain)
    context['data_source_options_map'] = form.data_source_options_map
    context['form'] = form
    return render(request, 'userreports/data_source_from_app.html', context)


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def create_form_data_source_from_app(request, domain):
    if request.method == 'POST':
        form = ConfigurableFormDataSourceFromAppForm(domain, request.POST)
        if form.is_valid():
            # save config
            data_source = get_form_data_source(form.app, form.form)
            data_source.save()
            messages.success(request, _(u"Data source created for '{}'".format(form.form.default_name())))
            return HttpResponseRedirect(reverse('edit_configurable_data_source', args=[domain, data_source._id]))
    else:
        form = ConfigurableFormDataSourceFromAppForm(domain)
    context = _shared_context(domain)
    context['form'] = form
    context['data_source_options_map'] = form.data_source_options_map
    return render(request, 'userreports/data_source_from_app.html', context)


def _edit_data_source_shared(request, domain, config, read_only=False):
    if request.method == 'POST':
        form = ConfigurableDataSourceEditForm(domain, config, request.POST)
        if form.is_valid():
            config = form.save(commit=True)
            messages.success(request, _(u'Data source "{}" saved!').format(config.display_name))
    else:
        form = ConfigurableDataSourceEditForm(domain, config, read_only=read_only)
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


@login_and_domain_required
def export_data_source(request, domain, config_id):
    format = request.GET.get('format', Format.UNZIPPED_CSV)
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    table = get_indicator_table(config)
    q = Session.query(table)
    column_headers = [col['name'] for col in q.column_descriptions]

    # apply filtering if any
    filter_values = {key: value for key, value in request.GET.items() if key != 'format'}
    for key in filter_values:
        if key not in column_headers:
            return HttpResponse('Invalid filter parameter: {}'.format(key), status=400)
    q = q.filter_by(**filter_values)

    # build export
    def get_table(q):
        yield column_headers
        for row in q:
            yield row

    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as temp:
        export_from_tables([[config.table_id, get_table(q)]], temp, format)
        return export_response(Temp(path), format, config.display_name)


@login_and_domain_required
def data_source_status(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    return json_response({'isBuilt': config.meta.build.built})


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
