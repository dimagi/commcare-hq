import urllib
from collections import namedtuple
import datetime
import functools
import json
import os
import tempfile
import uuid

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.http import HttpResponseRedirect, HttpResponse
from django.http.response import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import View


from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
from sqlalchemy import types, exc
from sqlalchemy.exc import ProgrammingError

from corehq.apps.accounting.models import Subscription
from corehq.apps.analytics.tasks import update_hubspot_properties
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.util import reverse
from corehq.util.quickcache import quickcache
from couchexport.export import export_from_tables
from couchexport.files import Temp
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.dbaccessors import domain_has_apps
from corehq.apps.app_manager.models import Application, Form
from corehq.apps.app_manager.util import purge_report_from_mobile_ucr
from corehq.apps.dashboard.models import IconContext, TileConfiguration, Tile
from corehq.apps.domain.decorators import login_and_domain_required, login_or_basic
from corehq.apps.locations.permissions import conditionally_location_safe
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.reports.dispatcher import cls_to_view_login_and_domain
from corehq.apps.style.decorators import (
    use_select2,
    use_daterangepicker,
    use_datatables,
    use_jquery_ui,
    use_angular_js,
)
from corehq.apps.userreports.app_manager import get_case_data_source, get_form_data_source, _clean_table_name
from corehq.apps.userreports.const import REPORT_BUILDER_EVENTS_KEY, DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE
from corehq.apps.userreports.exceptions import (
    BadBuilderConfigError,
    BadSpecError,
    DataSourceConfigurationNotFoundError,
    ReportConfigurationNotFoundError,
    UserQueryError,
)
from corehq.apps.userreports.models import (
    ReportConfiguration,
    DataSourceConfiguration,
    StaticReportConfiguration,
    StaticDataSourceConfiguration,
    get_datasource_config,
    get_report_config,
    report_config_id_is_static,
    id_is_static,
    DataSourceMeta,
    DataSourceBuildInformation,
    ReportMeta,
)
from corehq.apps.userreports.rebuild import DataSourceResumeHelper
from corehq.apps.userreports.reports.builder.forms import (
    DataSourceForm,
    ConfigureMapReportForm,
    DataSourceBuilder,
)
from corehq.apps.userreports.reports.filters.choice_providers import (
    ChoiceQueryContext,
)
from corehq.apps.userreports.reports.view import ConfigurableReport
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.tasks import rebuild_indicators, resume_building_indicators
from corehq.apps.userreports.ui.forms import (
    ConfigurableReportEditForm,
    ConfigurableDataSourceEditForm,
    ConfigurableDataSourceFromAppForm,
)
from corehq.apps.userreports.util import (
    add_event,
    get_indicator_adapter,
    has_report_builder_access,
    has_report_builder_add_on_privilege,
    allowed_report_builder_reports,
    number_of_report_builder_reports
)
from corehq.apps.userreports.reports.util import has_location_filter
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.util.couch import get_document_or_404


SAMPLE_DATA_MAX_ROWS = 100
TEMP_REPORT_PREFIX = '__tmp'


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


def swallow_programming_errors(fn):
    @functools.wraps(fn)
    def decorated(request, domain, *args, **kwargs):
        try:
            return fn(request, domain, *args, **kwargs)
        except ProgrammingError as e:
            if settings.DEBUG:
                raise
            messages.error(
                request,
                _('There was a problem processing your request. '
                  'If you have recently modified your report data source please try again in a few minutes.'
                  '<br><br>Technical details:<br>{}'.format(e)),
                extra_tags='html',
            )
            return HttpResponseRedirect(reverse('configurable_reports_home', args=[domain]))
    return decorated


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

    @property
    def page_context(self):
        return {}


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


class CreateConfigReportView(BaseEditConfigReportView):
    urlname = 'create_configurable_report'
    page_title = ugettext_lazy("Create Report")


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
        return reverse(ReportBuilderDataSourceSelect.urlname, args=[self.domain])


@quickcache(["domain"], timeout=0, memoize_timeout=4)
def paywall_home(domain):
    """
    Return the url for the page in the report builder paywall that users
    in the given domain should be directed to upon clicking "+ Create new report"
    """
    project = Domain.get_by_name(domain, strict=True)
    if project.requested_report_builder_subscription:
        return reverse(ReportBuilderPaywallActivatingSubscription.urlname, args=[domain])
    else:
        return reverse(ReportBuilderPaywallPricing.urlname, args=[domain])


class ReportBuilderPaywallBase(BaseDomainView):
    page_title = ugettext_lazy('Subscribe')

    @property
    def section_name(self):
        return _("Report Builder")

    @property
    def section_url(self):
        return paywall_home(self.domain)

    @property
    def page_context(self):
        context = super(ReportBuilderPaywallBase, self).page_context
        context.update({
            'support_email': settings.SUPPORT_EMAIL
        })
        return context

    @property
    @memoized
    def plan_name(self):
        plan_version, _ = Subscription.get_subscribed_plan_by_domain(self.domain)
        return plan_version.plan.name


class ReportBuilderPaywallPricing(ReportBuilderPaywallBase):
    template_name = "userreports/paywall/pricing.html"
    urlname = 'report_builder_paywall_pricing'
    page_title = ugettext_lazy('Pricing')

    @property
    def page_context(self):
        context = super(ReportBuilderPaywallPricing, self).page_context
        if has_report_builder_access(self.request):
            max_allowed_reports = allowed_report_builder_reports(self.request)
            num_builder_reports = number_of_report_builder_reports(self.domain)
            if num_builder_reports >= max_allowed_reports:
                context.update({
                    'at_report_limit': True,
                    'max_allowed_reports': max_allowed_reports,

                })
        return context


class ReportBuilderPaywallActivatingSubscription(ReportBuilderPaywallBase):
    template_name = "userreports/paywall/activating_subscription.html"
    urlname = 'report_builder_paywall_activating_subscription'

    def post(self, request, domain, *args, **kwargs):
        self.domain_object.requested_report_builder_subscription.append(request.user.username)
        self.domain_object.save()
        send_mail_async.delay(
            "Report Builder Subscription Request: {}".format(domain),
            "User {} in the {} domain has requested a report builder subscription."
            " Current subscription is '{}'.".format(
                request.user.username,
                domain,
                self.plan_name
            ),
            settings.DEFAULT_FROM_EMAIL,
            [settings.REPORT_BUILDER_ADD_ON_EMAIL],
        )
        update_hubspot_properties.delay(request.couch_user, {'report_builder_subscription_request': 'yes'})
        return self.get(request, domain, *args, **kwargs)


# TODO: kill
class ReportBuilderTypeSelect(JSONResponseMixin, ReportBuilderView):
    template_name = "userreports/reportbuilder/report_type_select.html"
    urlname = 'report_builder_select_type'
    page_title = ugettext_lazy('Select Report Type')

    @use_angular_js
    def dispatch(self, request, *args, **kwargs):
        max_allowed_reports = allowed_report_builder_reports(self.request)
        num_builder_reports = number_of_report_builder_reports(self.domain)
        if num_builder_reports >= max_allowed_reports:
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
    template_name = 'userreports/reportbuilder/data_source_select.html'
    page_title = ugettext_lazy('Create Report')
    urlname = 'report_builder_select_source'

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
            return DataSourceForm(self.domain, max_allowed_reports, self.request.POST)
        return DataSourceForm(self.domain, max_allowed_reports)

    def _get_config_kwargs(self, app_source):
        app = Application.get(app_source.application)
        builder = DataSourceBuilder(self.domain, app, app_source.source_type, app_source.source)
        return {
            'display_name': builder.data_source_name,
            'referenced_doc_type': builder.source_doc_type,
            'configured_filter': builder.filter,
            'configured_indicators': builder.indicators(),
            'base_item_expression': builder.base_item_expression(False),
            'meta': DataSourceMeta(
                build=DataSourceBuildInformation(
                    source_id=app_source.source,
                    app_id=app._id,
                    app_version=app.version,
                )
            )
        }

    def _build_data_source(self, app_source, username):
        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            table_id=_clean_table_name(self.domain, uuid.uuid4().hex),
            **self._get_config_kwargs(app_source)
        )
        data_source_config.validate()
        data_source_config.save()
        rebuild_indicators(data_source_config._id, username, limit=SAMPLE_DATA_MAX_ROWS)  # Do synchronously
        return data_source_config._id

    @staticmethod
    def filter_data_source_changes(data_source_config_id):
        """
        Add filter to data source to prevent it from being updated by DB changes
        """
        # Reload using the ID instead of just passing in the object to avoid ResourceConflicts
        data_source_config = DataSourceConfiguration.get(data_source_config_id)
        data_source_config.configured_filter.update({
            'type': 'constant',
            'constant': False
        })
        data_source_config.save()

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            app_source = self.form.get_selected_source()
            data_source_config_id = self._build_data_source(app_source, request.user.username)
            self.filter_data_source_changes(data_source_config_id)

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

            get_params = {
                'report_name': self.form.cleaned_data['report_name'],
                'application': app_source.application,
                'source_type': app_source.source_type,
                'source': app_source.source,
                'data_source': data_source_config_id,
            }
            return HttpResponseRedirect(
                reverse(ConfigureReport.urlname, args=[self.domain], params=get_params)
            )
        else:
            return self.get(request, *args, **kwargs)


class EditReportInBuilder(View):

    def dispatch(self, request, *args, **kwargs):
        report_id = kwargs['report_id']
        report = get_document_or_404(ReportConfiguration, request.domain, report_id)
        if report.report_meta.created_by_builder:
            try:
                return ConfigureReport.as_view(existing_report=report)(request, *args, **kwargs)
            except BadBuilderConfigError as e:
                messages.error(request, e.message)
                return HttpResponseRedirect(reverse(ConfigurableReport.slug, args=[request.domain, report_id]))
        raise Http404("Report was not created by the report builder")


def to_report_column(column):
    """
    column is the JSON that we get when saving or previewing a report. Return a column spec we can use to create a
    ReportConfiguration.
    """
    # Example value of column:
    #     {
    #         u'column_id': u'modified_on_6457b79c',
    #         u'name': u'modified_on'
    #         u'label': u'modified on',
    #         u'is_numeric': False,
    #         u'is_group_by_column': False,
    #         u'aggregation': None,
    #     }
    return {
        'aggregation': column.get('aggregation') or 'simple',
        'field': column['column_id'],
        'display': column['label'],
        'type': 'field',
        'format': 'default',
    }


class ConfigureReport(ReportBuilderView):
    urlname = 'configure_report'
    page_title = ugettext_lazy("Configure Report")
    template_name = "userreports/reportbuilder/configure_report.html"
    url_args = ['report_name', 'application', 'source_type', 'source']
    report_title = '{}'
    existing_report = None

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(ConfigureReport, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        title = self.request.GET.get('report_name', '')
        if self.existing_report:
            title = self.existing_report.title
        return _(self.report_title).format(title)

    def get_columns(self):
        builder = DataSourceBuilder(
            self.domain,
            Application.get(self.request.GET['application']),
            self.request.GET['source_type'],
            self.request.GET['source']
        )
        return [{
            'column_id': v.column_id,
            'name': k,
            'label': v.text,
            'is_numeric': not v.is_non_numeric,
        } for k, v in builder.data_source_properties.iteritems()]

    @property
    def page_context(self):
        return {
            'report': {
                "title": self.page_name
            },
            'columns': self.get_columns(),
            'source_type': self.request.GET['source_type'],
            'data_source_url': reverse(ReportPreview.urlname,
                                       args=[self.domain, self.request.GET['data_source']]),
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

    def post(self, request, domain):

        def get_data_source_configuration_kwargs(ds_builder_, app_, report_source_id_, report_data_):
            aggregation_fields = [c['column_id'] for c in report_data_['columns'] if c['is_group_by_column']]
            is_multiselect_chart_report = False  # report_data_['isAggregationEnabled']  # Not the same thing
            if is_multiselect_chart_report:
                base_item_expression = ds_builder_.base_item_expression(True, aggregation_fields[0])
            else:
                base_item_expression = ds_builder_.base_item_expression(False)
            number_columns = [c['column_id'] for c in report_data_['columns'] if c['is_numeric']]
            return dict(
                display_name=ds_builder_.data_source_name,
                referenced_doc_type=ds_builder_.source_doc_type,
                configured_filter=ds_builder_.filter,
                configured_indicators=ds_builder_.indicators(
                    number_columns, is_multiselect_chart_report
                ),
                base_item_expression=base_item_expression,
                meta=DataSourceMeta(build=DataSourceBuildInformation(
                    source_id=report_source_id_,
                    app_id=app_._id,
                    app_version=app_.version,
                ))
            )

        def build_data_source(domain_, ds_config_kwargs_):
            data_source_config = DataSourceConfiguration(
                domain=domain_,
                # The uuid gets truncated, so it's not really universally unique.
                table_id=_clean_table_name(domain_, str(uuid.uuid4().hex)),
                **ds_config_kwargs_,
            )
            data_source_config.validate()
            data_source_config.save()
            rebuild_indicators.delay(data_source_config._id)
            return data_source_config._id

        def get_report_charts(report_data_):
            report_type_funcs = {
                'bar': lambda cols: [{
                    'type': 'multibar',
                    'x_axis_column': [c['column_id'] for c in cols if c['is_group_by_column']][0],  # 1st group by
                    'y_axis_columns': [c['column_id'] for c in cols if not c['is_group_by_column']],
                }],
                'pie': lambda cols: [{
                    "type": "pie",
                    "aggregation_column": [c['column_id'] for c in cols if c['is_group_by_column']][0],
                    "value_column": [c['column_id'] for c in cols if not c['is_group_by_column']][0],
                }],
                'none': lambda cols: [],
            }
            func = report_type_funcs[report_data_['report_type']]
            return func(report_data_['columns'])

        self._confirm_report_limit()

        report_name = request.GET['report_name']
        source_type = request.GET['source_type']
        report_source_id = request.GET['source']
        # data_source_id = request.GET['data_source']  # TODO: Why is this a GET param if it's unused?
        app = Application.get(request.GET['application'])

        report_data = json.loads(request.body)

        ds_builder = DataSourceBuilder(app.domain, app, source_type, report_source_id)
        ds_config_kwargs = get_data_source_configuration_kwargs(ds_builder, app, report_source_id, report_data)
        data_source_config_id = build_data_source(app.domain, ds_config_kwargs)

        self._confirm_report_limit()
        try:
            if report_data['aggregate']:
                aggregation_columns = [c['column_id'] for c in report_data['columns'] if c['is_group_by_column']]
            else:
                aggregation_columns = []
            report_configuration = ReportConfiguration(
                domain=app.domain,
                config_id=data_source_config_id,
                title=report_name,
                aggregation_columns=aggregation_columns,
                columns=[to_report_column(c) for c in report_data['columns']],
                filters=[],  # TODO: report_data['user_filters'] + report_data['default_filters']
                configured_charts=get_report_charts(report_data),
                report_meta=ReportMeta(
                    created_by_builder=True,
                    builder_report_type=report_data['report_type'],
                )
            )
            report_configuration.validate()
            report_configuration.save()
        except BadSpecError as err:
            messages.error(request, str(err))
            notify_exception(request, str(err), details={
                'domain': domain,
                'report_type': report_data['report_type'],
                # 'group_by': getattr(self.report_form, 'group_by', 'Not set'),
                # 'user_filters': getattr(self.report_form, 'user_filters', 'Not set'),
                # 'default_filters': getattr(self.report_form, 'default_filters', 'Not set'),
            })
            return self.get(request, domain)
        return HttpResponseRedirect(
            reverse(ConfigurableReport.slug, args=[self.domain, report_configuration._id])
        )

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


class ReportPreview(BaseDomainView):
    urlname = 'report_preview'

    def post(self, request, domain, data_source):
        report_data = json.loads(urllib.unquote(request.body))
        if report_data['aggregate']:
            aggregation_columns = [c['column_id'] for c in report_data['columns'] if c['is_group_by_column']]
        else:
            aggregation_columns = []
        table = ConfigurableReport.report_config_table(
            domain=domain,
            config_id=data_source,
            title='{}_{}_{}'.format(TEMP_REPORT_PREFIX, domain, data_source),
            description='',
            aggregation_columns=aggregation_columns,
            columns=[to_report_column(c) for c in report_data['columns']],
            report_meta=ReportMeta(created_by_builder=True),
        )
        return json_response(table[0][1])


class ConfigureMapReport(ConfigureReport):
    urlname = 'configure_map_report'
    report_title = ugettext_lazy("Map Report: {}")
    report_type = 'map'

    @property
    @memoized
    def configuration_form_class(self):
        return ConfigureMapReportForm


def delete_report(request, domain, report_id):
    if not (toggle_enabled(request, toggles.USER_CONFIGURABLE_REPORTS)
            or toggle_enabled(request, toggles.REPORT_BUILDER)
            or toggle_enabled(request, toggles.REPORT_BUILDER_BETA_GROUP)
            or has_report_builder_add_on_privilege(request)):
        raise Http404()

    config = get_document_or_404(ReportConfiguration, domain, report_id)

    # Delete the data source too if it's not being used by any other reports.
    try:
        data_source, __ = get_datasource_config(config.config_id, domain)
    except DataSourceConfigurationNotFoundError:
        # It's possible the data source has already been deleted, but that's fine with us.
        pass
    else:
        if data_source.get_report_count() <= 1:
            # No other reports reference this data source.
            data_source.deactivate()

    config.delete()
    did_purge_something = purge_report_from_mobile_ucr(config)

    messages.success(request, _(u'Report "{}" deleted!').format(config.title))
    if did_purge_something:
        messages.warning(
            request,
            _(u"This report was used in one or more applications. "
              "It has been removed from there too.")
        )
    redirect = request.GET.get("redirect", None)
    if not redirect:
        redirect = reverse('configurable_reports_home', args=[domain])
    return HttpResponseRedirect(redirect)


class ImportConfigReportView(BaseUserConfigReportsView):
    page_title = ugettext_lazy("Import Report")
    template_name = "userreports/import_report.html"
    urlname = 'import_configurable_report'

    @property
    def spec(self):
        if self.request.method == "POST":
            return self.request.POST['report_spec']
        return ''

    def post(self, request, *args, **kwargs):
        try:
            json_spec = json.loads(self.spec)
            if '_id' in json_spec:
                del json_spec['_id']
            json_spec['domain'] = self.domain
            report = ReportConfiguration.wrap(json_spec)
            report.validate()
            report.save()
            messages.success(request, _('Report created!'))
            return HttpResponseRedirect(reverse(
                EditConfigReportView.urlname, args=[self.domain, report._id]
            ))
        except (ValueError, BadSpecError) as e:
            messages.error(request, _('Bad report source: {}').format(e))
        return self.get(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'spec': self.spec,
        }


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def report_source_json(request, domain, report_id):
    config, _ = get_report_config_or_404(report_id, domain)
    config._doc.pop('_rev', None)
    return json_response(config)


class CreateDataSourceFromAppView(BaseUserConfigReportsView):
    urlname = 'create_configurable_data_source_from_app'
    template_name = "userreports/data_source_from_app.html"
    page_title = ugettext_lazy("Create Data Source from Application")

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return ConfigurableDataSourceFromAppForm(self.domain, self.request.POST)
        return ConfigurableDataSourceFromAppForm(self.domain)

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            app_source = self.form.app_source_helper.get_app_source(self.form.cleaned_data)
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

            return HttpResponseRedirect(reverse(
                EditDataSourceView.urlname, args=[self.domain, data_source._id]
            ))
        return self.get(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'sources_map': self.form.app_source_helper.all_sources,
            'form': self.form,
        }


class BaseEditDataSourceView(BaseUserConfigReportsView):
    template_name = 'userreports/edit_data_source.html'

    @property
    def page_context(self):
        return {
            'form': self.edit_form,
            'data_source': self.config,
            'read_only': self.read_only,
            'code_mirror_off': self.request.GET.get('code_mirror', 'true') == 'false',
        }

    @property
    def page_url(self):
        if self.config_id:
            return reverse(self.urlname, args=(self.domain, self.config_id,))
        return super(BaseEditDataSourceView, self).page_url

    @property
    def config_id(self):
        return self.kwargs.get('config_id')

    @property
    def read_only(self):
        return id_is_static(self.config_id) if self.config_id is not None else False

    @property
    @memoized
    def config(self):
        if self.config_id is None:
            return DataSourceConfiguration(domain=self.domain)
        return get_datasource_config_or_404(self.config_id, self.domain)[0]

    @property
    @memoized
    def edit_form(self):
        if self.request.method == 'POST':
            return ConfigurableDataSourceEditForm(
                self.domain,
                self.config,
                self.read_only,
                data=self.request.POST
            )
        return ConfigurableDataSourceEditForm(
            self.domain, self.config, self.read_only
        )

    def post(self, request, *args, **kwargs):
        if self.edit_form.is_valid():
            config = self.edit_form.save(commit=True)
            messages.success(request, _(u'Data source "{}" saved!').format(
                config.display_name
            ))
            if self.config_id is None:
                return HttpResponseRedirect(reverse(
                    EditDataSourceView.urlname, args=[self.domain, config._id])
                )
        return self.get(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.config.is_deactivated:
            messages.info(
                request, _(
                    'Data source "{}" has no associated table.\n'
                    'Click "Rebuild Data Source" to recreate the table.'
                ).format(self.config.display_name)
            )
        return super(BaseEditDataSourceView, self).get(request, *args, **kwargs)


class CreateDataSourceView(BaseEditDataSourceView):
    urlname = 'create_configurable_data_source'
    page_title = ugettext_lazy("Create Data Source")


class EditDataSourceView(BaseEditDataSourceView):
    urlname = 'edit_configurable_data_source'
    page_title = ugettext_lazy("Edit Data Source")

    @property
    def page_name(self):
        return "Edit {}".format(self.config.display_name)


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
@require_POST
def delete_data_source(request, domain, config_id):
    delete_data_source_shared(domain, config_id, request)
    return HttpResponseRedirect(reverse('configurable_reports_home', args=[domain]))


def delete_data_source_shared(domain, config_id, request=None):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id)
    adapter = get_indicator_adapter(config)
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
    if config.is_deactivated:
        config.is_deactivated = False
        config.save()

    messages.success(
        request,
        _('Table "{}" is now being rebuilt. Data should start showing up soon').format(
            config.display_name
        )
    )

    rebuild_indicators.delay(config_id, request.user.username)
    return HttpResponseRedirect(reverse(
        EditDataSourceView.urlname, args=[domain, config._id]
    ))


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
@require_POST
def resume_building_data_source(request, domain, config_id):
    config, is_static = get_datasource_config_or_404(config_id, domain)
    if not is_static and config.meta.build.finished:
        messages.warning(
            request,
            _(u'Table "{}" has already finished building. Rebuild table to start over.').format(
                config.display_name
            )
        )
    elif not DataSourceResumeHelper(config).has_resume_info():
        messages.warning(
            request,
            _(u'Table "{}" did not finish building but resume information is not available. '
              u'Unfortunately, this means you need to rebuild the table.').format(
                config.display_name
            )
        )
    else:
        messages.success(
            request,
            _(u'Resuming rebuilding table "{}".').format(config.display_name)
        )
        resume_building_indicators.delay(config_id, request.user.username)
    return HttpResponseRedirect(reverse(
        EditDataSourceView.urlname, args=[domain, config._id]
    ))


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def data_source_json(request, domain, config_id):
    config, _ = get_datasource_config_or_404(config_id, domain)
    config._doc.pop('_rev', None)
    return json_response(config)


class PreviewDataSourceView(BaseUserConfigReportsView):
    urlname = 'preview_configurable_data_source'
    template_name = "userreports/preview_data.html"
    page_title = ugettext_lazy("Preview Data Source")

    @method_decorator(swallow_programming_errors)
    def dispatch(self, request, *args, **kwargs):
        return super(PreviewDataSourceView, self).dispatch(request, *args, **kwargs)

    @property
    def config_id(self):
        return self.kwargs['config_id']

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.config_id,))

    @property
    def page_context(self):
        config, is_static = get_datasource_config_or_404(self.config_id, self.domain)
        adapter = get_indicator_adapter(config)
        q = adapter.get_query_object()
        return {
            'data_source': config,
            'columns': q.column_descriptions,
            'data': q[:20],
            'total_rows': q.count(),
        }


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
@swallow_programming_errors
def export_data_source(request, domain, config_id):
    config, _ = get_datasource_config_or_404(config_id, domain)
    adapter = IndicatorSqlAdapter(config)
    q = adapter.get_query_object()
    table = adapter.get_table()

    try:
        params = process_url_params(request.GET, table.columns)
        allowed_formats = [
            Format.CSV,
            Format.HTML,
            Format.XLS,
            Format.XLS_2007,
        ]
        if params.format not in allowed_formats:
            msg = ugettext_lazy('format must be one of the following: {}').format(', '.join(allowed_formats))
            return HttpResponse(msg, status=400)
    except UserQueryError as e:
        return HttpResponse(e.message, status=400)

    q = q.filter_by(**params.keyword_filters)
    for sql_filter in params.sql_filters:
        q = q.filter(sql_filter)

    # xls format has limit of 65536 rows
    # First row is taken up by headers
    if params.format == Format.XLS and q.count() >= 65535:
        keyword_params = dict(**request.GET)
        # use default format
        if 'format' in keyword_params:
            del keyword_params['format']
        return HttpResponseRedirect(
            '%s?%s' % (
                reverse('export_configurable_data_source', args=[domain, config._id]),
                urlencode(keyword_params)
            )
        )

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
            msg = ugettext_lazy(
                "There was a problem executing your query, "
                "please make sure your parameters are valid."
            )
            return HttpResponse(msg, status=400)
        return export_response(Temp(path), params.format, config.display_name)


@login_and_domain_required
def data_source_status(request, domain, config_id):
    config, _ = get_datasource_config_or_404(config_id, domain)
    return json_response({'isBuilt': config.meta.build.finished})


def _get_report_filter(domain, report_id, filter_id):
    report = get_report_config_or_404(report_id, domain)[0]
    report_filter = report.get_ui_filter(filter_id)
    if report_filter is None:
        raise Http404(_(u'Filter {} not found!').format(filter_id))
    return report_filter


def _is_location_safe_choice_list(view_fn, domain, report_id, filter_id, **view_kwargs):
    return has_location_filter(view_fn, domain=domain, subreport_slug=report_id)


@login_and_domain_required
@conditionally_location_safe(_is_location_safe_choice_list)
def choice_list_api(request, domain, report_id, filter_id):
    report_filter = _get_report_filter(domain, report_id, filter_id)
    if hasattr(report_filter, 'choice_provider'):
        query_context = ChoiceQueryContext(
            query=request.GET.get('q', None),
            limit=int(request.GET.get('limit', 20)),
            page=int(request.GET.get('page', 1)) - 1,
            user=request.couch_user
        )
        return json_response([
            choice._asdict() for choice in
            report_filter.choice_provider.query(query_context)
        ])
    else:
        # mobile UCR hits this API for invalid filters. Just return no choices.
        return json_response([])


def _shared_context(domain):
    static_reports = list(StaticReportConfiguration.by_domain(domain))
    static_data_sources = list(StaticDataSourceConfiguration.by_domain(domain))
    return {
        'domain': domain,
        'reports': ReportConfiguration.by_domain(domain) + static_reports,
        'data_sources': DataSourceConfiguration.by_domain(domain) + static_data_sources,
    }
