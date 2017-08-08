
from __future__ import absolute_import

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy


from djangular.views.mixins import allow_remote_invocation

from corehq.apps.hqwebapp.views import HQJSONResponseMixin
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.reports.daterange import get_simple_dateranges
from corehq.apps.userreports.const import REPORT_BUILDER_EVENTS_KEY, DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE
from corehq.util import reverse
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception

from corehq import toggles
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.dbaccessors import domain_has_apps
from corehq.apps.dashboard.models import IconContext, TileConfiguration, Tile
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.reports.dispatcher import cls_to_view_login_and_domain
from corehq.apps.style.decorators import (
    use_select2,
    use_daterangepicker,
    use_datatables,
    use_jquery_ui,
    use_angular_js)
from corehq.apps.userreports.exceptions import (
    BadSpecError,
    DataSourceConfigurationNotFoundError,
    ReportConfigurationNotFoundError,
)
from corehq.apps.userreports.models import (
    ReportConfiguration,
    DataSourceConfiguration,
    StaticReportConfiguration,
    StaticDataSourceConfiguration,
    get_datasource_config,
    get_report_config,
    report_config_id_is_static,
)
from corehq.apps.userreports.reports.builder.v1.forms import (
    ConfigurePieChartReportForm,
    ConfigureTableReportForm,
    DataSourceForm,
    ConfigureBarChartReportForm,
    ConfigureListReportForm,
    ConfigureWorkerReportForm,
    ConfigureMapReportForm)
from corehq.apps.userreports.reports.view import ConfigurableReport
from corehq.apps.userreports.ui.forms import (
    ConfigurableReportEditForm,
)
from corehq.apps.userreports.util import (
    add_event,
    has_report_builder_access,
    allowed_report_builder_reports,
    number_of_report_builder_reports
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
import six


def get_datasource_config_or_404(config_id, domain):
    try:
        return get_datasource_config(config_id, domain)
    except DataSourceConfigurationNotFoundError:
        raise Http404


def get_report_config_or_404(config_id, domain):
    try:
        return get_report_config(config_id, domain)
    except ReportConfigurationNotFoundError:
        raise Http404


class BaseUserConfigReportsView(BaseDomainView):
    section_name = ugettext_lazy("Configurable Reports")

    @property
    def main_context(self):
        static_reports = list(StaticReportConfiguration.by_domain(self.domain))
        static_data_sources = list(StaticDataSourceConfiguration.by_domain(self.domain))
        context = super(BaseUserConfigReportsView, self).main_context
        context.update({
            'reports': ReportConfiguration.by_domain(self.domain) + static_reports,
            'data_sources': DataSourceConfiguration.by_domain(self.domain) + static_data_sources,
        })
        return context

    @property
    def section_url(self):
        return reverse(UserConfigReportsHomeView.urlname, args=(self.domain,))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @method_decorator(toggles.USER_CONFIGURABLE_REPORTS.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(BaseUserConfigReportsView, self).dispatch(request, *args, **kwargs)


class UserConfigReportsHomeView(BaseUserConfigReportsView):
    urlname = 'configurable_reports_home'
    template_name = 'userreports/configurable_reports_home.html'
    page_title = ugettext_lazy("Reports Home")


class BaseEditConfigReportView(BaseUserConfigReportsView):
    template_name = 'userreports/edit_report_config.html'

    @property
    def report_id(self):
        return self.kwargs.get('report_id')

    @property
    def page_url(self):
        if self.report_id:
            return reverse(self.urlname, args=(self.domain, self.report_id,))
        return super(BaseEditConfigReportView, self).page_url

    @property
    def page_context(self):
        return {
            'form': self.edit_form,
            'report': self.config,
            'code_mirror_off': self.request.GET.get('code_mirror', 'true') == 'false',
        }

    @property
    @memoized
    def config(self):
        if self.report_id is None:
            return ReportConfiguration(domain=self.domain)
        return get_report_config_or_404(self.report_id, self.domain)[0]

    @property
    def read_only(self):
        return report_config_id_is_static(self.report_id) if self.report_id is not None else False

    @property
    @memoized
    def edit_form(self):
        if self.request.method == 'POST':
            return ConfigurableReportEditForm(
                self.domain, self.config, self.read_only,
                data=self.request.POST)
        return ConfigurableReportEditForm(self.domain, self.config, self.read_only)

    def post(self, request, *args, **kwargs):
        if self.edit_form.is_valid():
            self.edit_form.save(commit=True)
            messages.success(request, _(u'Report "{}" saved!').format(self.config.title))
            return HttpResponseRedirect(reverse(
                'edit_configurable_report', args=[self.domain, self.config._id])
            )
        return self.get(request, *args, **kwargs)


class EditConfigReportView(BaseEditConfigReportView):
    urlname = 'edit_configurable_report'
    page_title = ugettext_lazy("Edit Report")


class ReportBuilderView(BaseDomainView):

    @method_decorator(require_permission(Permissions.edit_data))
    @cls_to_view_login_and_domain
    @use_select2
    @use_daterangepicker
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        if has_report_builder_access(request):
            return super(ReportBuilderView, self).dispatch(request, *args, **kwargs)
        else:
            raise Http404

    @property
    def section_name(self):
        return _("Report Builder")

    @property
    def section_url(self):
        return reverse(ReportBuilderTypeSelect.urlname, args=[self.domain])


class ReportBuilderTypeSelect(HQJSONResponseMixin, ReportBuilderView):
    template_name = "userreports/reportbuilder/report_type_select.html"
    urlname = 'report_builder_select_type'
    page_title = ugettext_lazy('Select Report Type')

    @use_angular_js
    def dispatch(self, request, *args, **kwargs):
        max_allowed_reports = allowed_report_builder_reports(self.request)
        num_builder_reports = number_of_report_builder_reports(self.domain)
        if num_builder_reports >= max_allowed_reports:
            from corehq.apps.userreports.views import ReportBuilderPaywallPricing
            return redirect(ReportBuilderPaywallPricing.urlname, self.domain)

        return super(ReportBuilderTypeSelect, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return "#"

    @property
    def page_context(self):
        return {
            "has_apps": domain_has_apps(self.domain),
            "report": {
                "title": _("Create New Report")
            },
            "tiles": [{
                'title': tile.title,
                'slug': tile.slug,
                'ng_directive': tile.ng_directive,
            } for tile in self.tiles],
        }

    @allow_remote_invocation
    def update_tile(self, in_data):
        tile = self.make_tile(in_data['slug'], in_data)
        return {
            'response': tile.context,
            'success': True,
        }

    def make_tile(self, slug, in_data):
        config = self.slug_to_tile[slug]
        return Tile(config, self.request, in_data)

    @property
    def slug_to_tile(self):
        return dict([(a.slug, a) for a in self.tiles])

    @property
    def tiles(self):
        clicked_tile = "Clicked on Report Builder Tile"
        tiles = [
            TileConfiguration(
                title=_('Chart'),
                slug='chart',
                analytics_usage_label="Chart",
                analytics_workflow_labels=[
                    clicked_tile,
                    "Clicked Chart Tile",
                ],
                icon='fcc fcc-piegraph-report',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'chart']),
                help_text=_('A bar graph or a pie chart to show data from your cases or forms.'
                            ' You choose the property to graph.'),
            ),
            TileConfiguration(
                title=_('Form or Case List'),
                slug='form-or-case-list',
                analytics_usage_label="List",
                analytics_workflow_labels=[
                    clicked_tile,
                    "Clicked Form or Case List Tile"
                ],
                icon='fcc fcc-form-report',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'list']),
                help_text=_('A list of cases or form submissions.'
                            ' You choose which properties will be columns.'),
            ),
            TileConfiguration(
                title=_('Worker Report'),
                slug='worker-report',
                analytics_usage_label="Worker",
                analytics_workflow_labels=[
                    clicked_tile,
                    "Clicked Worker Report Tile",
                ],
                icon='fcc fcc-user-report',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'worker']),
                help_text=_('A table of your mobile workers.'
                            ' You choose which properties will be the columns.'),
            ),
            TileConfiguration(
                title=_('Data Table'),
                slug='data-table',
                analytics_usage_label="Table",
                analytics_workflow_labels=[
                    clicked_tile,
                    "Clicked Data Table Tile"
                ],
                icon='fcc fcc-datatable-report',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'table']),
                help_text=_('A table of aggregated data from form submissions or case properties.'
                            ' You choose the columns and rows.'),
            ),
            TileConfiguration(
                title=_('Map'),
                slug='map',
                analytics_usage_label="Map",
                analytics_workflow_labels=[clicked_tile],
                icon='fcc fcc-globe',
                context_processor_class=IconContext,
                url=reverse('report_builder_select_source', args=[self.domain, 'map']),
                help_text=_('A map to show data from your cases or forms.'
                            ' You choose the property to map.'),
            )
        ]
        return tiles


class ReportBuilderDataSourceSelect(ReportBuilderView):
    template_name = 'userreports/reportbuilder/v1/data_source_select.html'
    page_title = ugettext_lazy('Create Report')

    @property
    def report_type(self):
        return self.kwargs['report_type']

    @property
    def page_context(self):
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
        max_allowed_reports = allowed_report_builder_reports(self.request)
        if self.request.method == 'POST':
            return DataSourceForm(self.domain, self.report_type, max_allowed_reports, self.request.POST)
        return DataSourceForm(self.domain, self.report_type, max_allowed_reports)

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            app_source = self.form.get_selected_source()
            url_names_map = {
                'list': 'configure_list_report',
                'chart': 'configure_chart_report',
                'table': 'configure_table_report',
                'worker': 'configure_worker_report',
                'map': 'configure_map_report',
            }
            url_name = url_names_map[self.report_type]
            get_params = {
                'report_name': self.form.cleaned_data['report_name'],
                'chart_type': self.form.cleaned_data['chart_type'],
                'application': app_source.application,
                'source_type': app_source.source_type,
                'source': app_source.source,
            }
            track_workflow(
                request.user.email,
                "Successfully submitted the first part of the Report Builder "
                "wizard where you give your report a name and choose a data source"
            )

            add_event(request, [
                "Report Builder",
                "Successful Click on Next (Data Source)",
                app_source.source_type,
            ])

            return HttpResponseRedirect(
                reverse(url_name, args=[self.domain], params=get_params)
            )
        else:
            return self.get(request, *args, **kwargs)


class ConfigureChartReport(ReportBuilderView):
    page_title = ugettext_lazy("Configure Report")
    template_name = "userreports/reportbuilder/v1/configure_report.html"
    url_args = ['report_name', 'application', 'source_type', 'source']
    report_title = ugettext_lazy("Chart Report: {}")
    report_type = 'chart'
    existing_report = None

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        if not self.existing_report and not (self.request.GET or self.request.POST):
            return HttpResponseRedirect(
                reverse('report_builder_select_source', args=[self.domain, self.report_type])
            )
        return super(ConfigureChartReport, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        title = self.request.GET.get('report_name', '')
        if self.existing_report:
            title = self.existing_report.title
        return _(self.report_title).format(title)

    @property
    def page_context(self):
        try:
            report_form = self.report_form
        except Exception as e:
            self.template_name = 'userreports/report_error.html'
            error_response = {
                'error_message': '',
                'details': six.text_type(e)
            }
            if self.existing_report is not None:
                error_response.update({
                    'report_id': self.existing_report.get_id,
                    'is_static': self.existing_report.is_static,
                })
            return self._handle_exception(error_response, e)
        field_names = report_form.fields.keys()
        return {
            'report': {
                "title": self.page_name
            },
            'report_type': self.report_type,
            'form': report_form,
            'is_group_by_required': 'group_by' in field_names or 'location' in field_names,
            'editing_existing_report': bool(self.existing_report),
            'report_column_options': [p.to_dict() for p in report_form.report_column_options.values()],
            'data_source_indicators': [p._asdict() for p in report_form.data_source_properties.values()],
            # For now only use date ranges that don't require additional parameters
            'date_range_options': [r._asdict() for r in get_simple_dateranges()],
            'initial_user_filters': [f._asdict() for f in report_form.initial_user_filters],
            'initial_default_filters': [f._asdict() for f in report_form.initial_default_filters],
            'initial_columns': [
                c._asdict() for c in getattr(report_form, 'initial_columns', [])
            ],
            'report_builder_events': self.request.session.pop(REPORT_BUILDER_EVENTS_KEY, [])
        }

    def _handle_exception(self, response, exception):
        if self.existing_report and self.existing_report.report_meta.edited_manually:
            error_message_base = _(
                'It looks like this report was edited by hand and is no longer editable in report builder.'
            )
            if toggle_enabled(self.request, toggles.USER_CONFIGURABLE_REPORTS):
                error_message = '{} {}'.format(error_message_base, _(
                    'You can edit the report manually using the <a href="{}">advanced UI</a>.'
                ).format(reverse(EditConfigReportView.urlname, args=[self.domain, self.existing_report._id])))
            else:
                error_message = '{} {}'.format(
                    error_message_base,
                    _('You can delete and recreate this report using the button below, or '
                      'report an issue if you believe you are seeing this page in error.')
                )
            response['error_message'] = error_message
            return response
        elif isinstance(exception, DataSourceConfigurationNotFoundError):
            response['details'] = None
            response['error_message'] = '{} {}'.format(
                str(exception),
                DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE
            )
            return response
        else:
            raise

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

    def _get_sum_avg_columns(self, columns):
        """
        Return a list of columns that have either sum or average aggregation types.
        Items in the list are tuples of (column['field'], column['aggregation']).
        """
        return [
            (col.get('field', None), col['aggregation'])
            for col in columns
            if col.get('aggregation', None) in ("sum", "average")
        ]

    def _track_invalid_form_events(self):
        group_by_errors = self.report_form.errors.as_data().get('group_by', [])
        if "required" in [e.code for e in group_by_errors]:
            add_event(self.request, [
                "Report Builder",
                "Click on Done (No Group By Chosen)",
                self.report_type,
            ])

    def _track_valid_form_events(self, existing_sum_avg_cols, report_configuration):
        if self.report_type != "chart":
            sum_avg_cols = self._get_sum_avg_columns(
                report_configuration.columns)
            # A column is "new" if there are no columns with the (property, agg) combo in the previous report
            if not set(sum_avg_cols).issubset(set(existing_sum_avg_cols)):
                add_event(self.request, [
                    "Report Builder",
                    "Changed Column Format to Sum or Average",
                    self.report_type,
                ])

    def _track_new_report_events(self):
        track_workflow(
            self.request.user.email,
            "Successfully created a new report in the Report Builder"
        )
        add_event(self.request, [
            "Report Builder",
            "Click On Done On New Report (Successfully)",
            self.report_type,
        ])

    def post(self, *args, **kwargs):
        if self.report_form.is_valid():
            existing_sum_avg_cols = []
            if self.report_form.existing_report:
                try:
                    existing_sum_avg_cols = self._get_sum_avg_columns(
                        self.report_form.existing_report.columns
                    )
                    report_configuration = self.report_form.update_report()
                except ValidationError as e:
                    messages.error(self.request, e.message)
                    return self.get(*args, **kwargs)
            else:
                self._confirm_report_limit()
                try:
                    report_configuration = self.report_form.create_report()
                except BadSpecError as err:
                    messages.error(self.request, str(err))
                    notify_exception(self.request, str(err), details={
                        'domain': self.domain,
                        'report_form_class': self.report_form.__class__.__name__,
                        'report_type': self.report_form.report_type,
                        'group_by': getattr(self.report_form, 'group_by', 'Not set'),
                        'user_filters': getattr(self.report_form, 'user_filters', 'Not set'),
                        'default_filters': getattr(self.report_form, 'default_filters', 'Not set'),
                    })
                    return self.get(*args, **kwargs)
                self._track_new_report_events()

            self._track_valid_form_events(existing_sum_avg_cols, report_configuration)
            return HttpResponseRedirect(
                reverse(ConfigurableReport.slug, args=[self.domain, report_configuration._id])
            )
        else:
            self._track_invalid_form_events()

        return self.get(*args, **kwargs)

    def _confirm_report_limit(self):
        """
        This method is used to confirm that the user is not creating more reports
        than they are allowed.
        The user is normally turned back earlier in the process, but this check
        is necessary in case they navigated directly to this view either
        maliciously or with a bookmark perhaps.
        """
        if (number_of_report_builder_reports(self.domain) >=
                allowed_report_builder_reports(self.request)):
            raise Http404()


class ConfigureListReport(ConfigureChartReport):
    report_title = ugettext_lazy("List Report: {}")
    report_type = 'list'

    @property
    @memoized
    def configuration_form_class(self):
        return ConfigureListReportForm


class ConfigureTableReport(ConfigureChartReport):
    report_title = ugettext_lazy("Table Report: {}")
    report_type = 'table'

    @property
    @memoized
    def configuration_form_class(self):
        return ConfigureTableReportForm


class ConfigureWorkerReport(ConfigureChartReport):
    report_title = ugettext_lazy("Worker Report: {}")
    report_type = 'worker'

    @property
    @memoized
    def configuration_form_class(self):
        return ConfigureWorkerReportForm


class ConfigureMapReport(ConfigureChartReport):
    report_title = ugettext_lazy("Map Report: {}")
    report_type = 'map'

    @property
    @memoized
    def configuration_form_class(self):
        return ConfigureMapReportForm

