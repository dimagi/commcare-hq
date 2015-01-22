import json
from oauth2 import escape
from dimagi.utils.decorators.memoized import memoized
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.views.generic import View, TemplateView
from corehq.apps.reports.dispatcher import cls_to_view_login_and_domain
from corehq.apps.app_manager.models import get_apps_in_domain
from corehq import Session, ConfigurableReport
from corehq import toggles
from corehq.apps.userreports.app_manager import get_case_data_source, get_form_data_source
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.forms import CreateNewReportBuilderForm, \
    ConfigureBarChartBuilderForm
from corehq.apps.userreports.models import ReportConfiguration, DataSourceConfiguration
from corehq.apps.userreports.sql import get_indicator_table, IndicatorSqlAdapter, get_engine
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.ui.forms import ConfigurableReportEditForm, ConfigurableDataSourceEditForm, \
    ConfigurableDataSourceFromAppForm, ConfigurableFormDataSourceFromAppForm
from corehq.util.couch import get_document_or_404
from dimagi.utils.web import json_response


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
            "case_type_map": {
                app._id: {
                    "case": list(app.get_case_types()),
                    "form": [form.get_unique_id() for form in app.get_forms()]
                } for app in apps
            },
            "domain": self.domain,
            'report': {"title": _("Create New Report")},
            'form': self.create_new_report_builder_form,
        }
        return context

    @property
    @memoized
    def create_new_report_builder_form(self):
        if self.request.method == 'POST':
            return CreateNewReportBuilderForm(self.domain, self.request.POST)
        return CreateNewReportBuilderForm(self.domain)

    def post(self, request, *args, **kwargs):
        if self.create_new_report_builder_form.is_valid():
            if self.create_new_report_builder_form.cleaned_data['report_type'] == 'bar_chart':
                return HttpResponseRedirect(
                    reverse(
                        'configure_bar_chart_report_builder',
                        args=[self.domain],
                    ) + '?report_source=%s' % escape(
                        self.create_new_report_builder_form.cleaned_data['report_source']
                    ) + '&source_type=%s' % self.create_new_report_builder_form.cleaned_data['source_type']
                )
        else:
            return self.get(request, *args, **kwargs)


class ConfigureBarChartReportBuilderView(ReportBuilderView):
    template_name = "userreports/base_report_builder.html"

    def get_context_data(self, **kwargs):
        context = {
            "domain": self.domain,
            'report': {"title": _("Create New Report > Configure Bar Chart Report")},
            'form': self.configure_bar_chart_builder_form,
        }
        return context

    @property
    @memoized
    def configure_bar_chart_builder_form(self):
        if self.request.method == 'POST':
            source_type = self.request.POST.get('source_type', '')
            report_source = self.request.POST.get('report_source', '')
            return ConfigureBarChartBuilderForm(self.domain, source_type, report_source, self.request.POST)
        source_type = self.request.GET.get('source_type', '')
        report_source = self.request.GET.get('report_source', '')
        return ConfigureBarChartBuilderForm(self.domain, source_type, report_source)


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
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    return _edit_data_source_shared(request, domain, config)


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
    return render(request, 'userreports/data_source_from_app.html', context)


def _edit_data_source_shared(request, domain, config):
    if request.method == 'POST':
        form = ConfigurableDataSourceEditForm(domain, config, request.POST)
        if form.is_valid():
            config = form.save(commit=True)
            messages.success(request, _(u'Data source "{}" saved!').format(config.display_name))
    else:
        form = ConfigurableDataSourceEditForm(domain, config)
    context = _shared_context(domain)
    context.update({
        'form': form,
        'data_source': config,
    })
    return render(request, "userreports/edit_data_source.html", context)


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
@require_POST
def delete_data_source(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    adapter = IndicatorSqlAdapter(get_engine(), config)
    adapter.drop_table()
    config.delete()
    messages.success(request,
                     _(u'Data source "{}" has been deleted.'.format(config.display_name)))
    return HttpResponseRedirect(reverse('configurable_reports_home', args=[domain]))


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
@require_POST
def rebuild_data_source(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
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
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
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


def choice_list_api(request, domain, report_id, filter_id):
    report = get_document_or_404(ReportConfiguration, domain, report_id)
    filter = report.get_ui_filter(filter_id)

    def get_choices(data_source, filter, search_term=None, limit=20):
        table = get_indicator_table(data_source)
        sql_column = table.c[filter.name]
        query = Session.query(sql_column)
        if search_term:
            query = query.filter(sql_column.contains(search_term))

        return [v[0] for v in query.distinct().limit(limit)]

    return json_response(get_choices(report.config, filter, request.GET.get('q', None)))


def _shared_context(domain):
    return {
        'domain': domain,
        'reports': ReportConfiguration.by_domain(domain),
        'data_sources': DataSourceConfiguration.by_domain(domain),
    }
