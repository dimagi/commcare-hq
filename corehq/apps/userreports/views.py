import urllib
from collections import namedtuple, OrderedDict
import datetime
import functools
import json
import os
import tempfile
import uuid
from itertools import chain

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
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
from corehq.apps.userreports.reports.builder import get_filter_format_from_question_type
from corehq.apps.userreports.reports.builder.columns import ColumnOption, MultiselectQuestionColumnOption, \
    QuestionColumnOption
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
    use_nvd3,
)
from corehq.apps.userreports.app_manager import get_case_data_source, get_form_data_source, _clean_table_name
from corehq.apps.userreports.const import REPORT_BUILDER_EVENTS_KEY, DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE
from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.exceptions import (
    BadBuilderConfigError,
    BadSpecError,
    DataSourceConfigurationNotFoundError,
    ReportConfigurationNotFoundError,
    UserQueryError,
)
from corehq.apps.userreports.expressions import ExpressionFactory
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
    REPORT_BUILDER_FILTER_TYPE_MAP, DefaultFilterViewModel, UserFilterViewModel)
from corehq.apps.userreports.reports.filters.choice_providers import (
    ChoiceQueryContext,
)
from corehq.apps.userreports.reports.view import ConfigurableReport
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.sql import IndicatorSqlAdapter, get_column_name
from corehq.apps.userreports.tasks import (
    rebuild_indicators,
    resume_building_indicators,
    delete_data_source_task,
)
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
    number_of_report_builder_reports,
)
from corehq.apps.userreports.reports.util import has_location_filter
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.util.couch import get_document_or_404
from pillowtop.dao.exceptions import DocumentNotFoundError


SAMPLE_DATA_MAX_ROWS = 100
TEMP_REPORT_PREFIX = '__tmp'
TEMP_DATA_SOURCE_LIFESPAN = 24 * 60 * 60


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

    def _expire_data_source(self, data_source_config_id):
        always_eager = settings.CELERY_ALWAYS_EAGER
        # CELERY_ALWAYS_EAGER will cause the data source to be deleted immediately. Switch it off temporarily
        settings.CELERY_ALWAYS_EAGER = False
        delete_data_source_task.apply_async(
            (self.domain, data_source_config_id),
            countdown=TEMP_DATA_SOURCE_LIFESPAN
        )
        settings.CELERY_ALWAYS_EAGER = always_eager

    def _build_temp_data_source(self, app_source, username):
        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            table_id=_clean_table_name(self.domain, uuid.uuid4().hex),
            **self._get_config_kwargs(app_source)
        )
        data_source_config.validate()
        data_source_config.save()
        self._expire_data_source(data_source_config._id)
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
            data_source_config_id = self._build_temp_data_source(app_source, request.user.username)
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


def to_report_columns(column, index, column_options):
    """
    column is the JSON that we get when saving or previewing a report. Return a column spec we can use to create a
    ReportConfiguration.
    """
    # Example value of column:
    #     {
    #         u'column_id': u'modified_on_6457b79c',
    #         u'name': u'modified_on'
    #         u'label': u'modified on',
    #         u'is_non_numeric': True,
    #         u'is_group_by_column': False,
    #         u'aggregation': None,
    #     }

    # Some wrangling in order to reused ColumnOption
    reverse_map = {v: k for k, v in ColumnOption.aggregation_map.items()}
    aggregation = reverse_map[column.get('aggregation') or 'simple']
    return column_options[column['column_id']].to_column_dicts(index, column['label'], aggregation)


def _get_aggregation_columns(aggregate, columns, column_options):
    if aggregate:
        aggregated_report_columns = [c['column_id'] for c in columns if c['is_group_by_column']]
        aggregation_columns = [column_options[c].indicator_id for c in aggregated_report_columns]
    else:
        aggregation_columns = ["doc_id"]
    return aggregation_columns


def _report_column_options(domain, application, source_type, source):
    builder = DataSourceBuilder(domain, application, source_type, source)
    options = OrderedDict()
    for id_, prop in builder.data_source_properties.iteritems():
        if prop.type == "question":
            if prop.source['type'] == "MSelect":
                option = MultiselectQuestionColumnOption(id_, prop.text, prop.column_id, prop.source)
            else:
                option = QuestionColumnOption(id_, prop.text, prop.column_id, prop.is_non_numeric,
                                              prop.source)
        else:
            # meta properties
            option = ColumnOption(id_, prop.text, prop.column_id, prop.is_non_numeric)
        options[id_] = option
    return options


class ConfigureReport(ReportBuilderView):
    urlname = 'configure_report'
    page_title = ugettext_lazy("Configure Report")
    template_name = "userreports/reportbuilder/configure_report.html"
    url_args = ['report_name', 'application', 'source_type', 'source']
    report_title = '{}'
    existing_report = None

    @use_jquery_ui
    @use_datatables
    @use_nvd3
    def dispatch(self, request, *args, **kwargs):
        if self.existing_report:
            self.source_type = {
                "CommCareCase": "case",
                "XFormInstance": "form"
            }[self.existing_report.config.referenced_doc_type]
            self.source_id = self.existing_report.config.meta.build.source_id
            self.app_id = self.existing_report.config.meta.build.app_id
            self.app = Application.get(self.app_id) if self.app_id else None
        else:
            self.app_id = self.request.GET['application']
            self.app = Application.get(self.app_id)
            self.source_type = self.request.GET['source_type']
            self.source_id = self.request.GET['source']

        self.data_source_builder = DataSourceBuilder(self.domain, self.app, self.source_type, self.source_id)
        self._properties_by_column = {
            p.column_id: p for p in self.data_source_builder.data_source_properties.values()
        }

        return super(ConfigureReport, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        title = self._get_report_name()
        return _(self.report_title).format(title)

    def _get_report_name(self, request=None):
        if self.existing_report:
            return self.existing_report.title
        else:
            request = request or self.request
            return request.GET.get('report_name', '')

    def _get_data_source(self, request=None):
        """
        Return the ID of the report's DataSourceConfiguration
        """
        if self.existing_report:
            return self.existing_report.config_id
        else:
            request = request or self.request
            return request.GET['data_source']

    @property
    @memoized
    def report_column_options(self):
        return _report_column_options(
            self.domain,
            self.app,
            self.source_type,
            self.source_id,
        )

    def get_column_option_dicts(self):
        columns = self.report_column_options
        # TODO: All the fields are called different things. Let's change it on the front end eventually,
        #       but re-map for now to see if its working

        def remap_fields(column):
            return {
                'column_id': column.id,
                'name': column.id,
                'label': column.display,
                'is_non_numeric': column._is_non_numeric
            }
        return map(remap_fields, columns.values())

    def _get_existing_report_type(self):
        # TODO: Handle map reports
        type_ = "list"
        if self.existing_report.aggregation_columns != ["doc_id"]:
            type_ = "agg"
        return type_

    def _column_exists(self, column_id):
        """
        Return True if this column corresponds to a question/case property in
        the current version of this form/case configuration.

        This could be true if a user makes a report, modifies the app, then
        edits the report.

        column_id is a string like "data_date_q_d1b3693e"
        """
        return column_id in [c.indicator_id for c in self.report_column_options.values()]

    def _data_source_prop_exists(self, indicator_id):
        """
        Return True if there exists a DataSourceProperty corresponding to the
        given data source indicator id.
        :param indicator_id:
        :return:
        """
        return indicator_id in self._properties_by_column

    def _get_property_id_by_indicator_id(self, indicator_column_id):
        """
        Return the data source property id corresponding to the given data
        source indicator column id.
        :param indicator_column_id: The column_id field of a data source indicator
            configuration dictionary
        :return: A DataSourceProperty property id, e.g. "/data/question1"
        """
        data_source_property = self._properties_by_column.get(indicator_column_id)
        if data_source_property:
            return data_source_property.id

    def _get_column_option_by_indicator_id(self, indicator_column_id):
        """
        Return the ColumnOption corresponding to the given indicator id.
        NOTE: This currently assumes that there is a one-to-one mapping between
        ColumnOptions and data source indicators, but we may want to remove
        this assumption as we add functionality to the report builder.
        :param indicator_column_id: The column_id field of a data source
            indicator configuration.
        :return: The corresponding ColumnOption
        """
        for column_option in self.report_column_options.values():
            if column_option.indicator_id == indicator_column_id:
                return column_option

    def _get_initial_columns(self):
        """
        Return a list of columns in the existing report.
        If there is no existing report, return None
        """
        # TODO: Do something different for aggregated reports etc. (search for initial_columns functions to see what I mean)
        # TODO: It would be nice to break this into smaller functions

        if self.existing_report:
            added_multiselect_columns = set()
            cols = []
            for c in self.existing_report.columns:
                mselect_indicator_id = _get_multiselect_indicator_id(
                    c['field'], self.existing_report.config.configured_indicators
                )
                indicator_id = mselect_indicator_id or c['field']
                display = c['display']
                exists = self._column_exists(indicator_id)

                if mselect_indicator_id:
                    if mselect_indicator_id not in added_multiselect_columns:
                        added_multiselect_columns.add(mselect_indicator_id)
                        display = MultiselectQuestionColumnOption.LABEL_DIVIDER.join(
                            display.split(MultiselectQuestionColumnOption.LABEL_DIVIDER)[:-1]
                        )
                    else:
                        continue
                cols.append({
                    "label": display,
                    "column_id": self._get_column_option_by_indicator_id(indicator_id).id if exists else None,
                    "name": self._get_column_option_by_indicator_id(indicator_id).id if exists else None,
                    "is_non_numeric": self._get_column_option_by_indicator_id(indicator_id)._is_non_numeric if exists else None,
                    "groupByOrAggregation": c.get('aggregation'),
                    # TODO: This should be one of sum, avg, simple, groupBy
                })
            return cols
        return None

    @property
    def page_context(self):
        return {
            'existing_report': self.existing_report,
            'report_title': self.page_name,
            'existing_report_type': self._get_existing_report_type(),

            # TODO: Consider renaming this because it's more like "possible" data source props
            'data_source_properties': [p._asdict() for p in self.data_source_builder.data_source_properties.values()],
            'initial_user_filters': [f._asdict() for f in self.get_initial_user_filters()],
            'initial_default_filters': [f._asdict() for f in self.get_initial_default_filters()],
            'column_options': self.get_column_option_dicts(),
            'initial_columns': self._get_initial_columns(),
            'source_type': self.source_type,
            'source_id': self.source_id,
            'application': self.app_id,
            'data_source_url': reverse(ReportPreview.urlname,
                                       args=[self.domain, self._get_data_source()]),
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

    def _get_aggregation_columns(self, report_data):
        return _get_aggregation_columns(
            report_data['aggregate'], report_data['columns'], self.report_column_options
        )

    @memoized
    def get_initial_default_filters(self):
        return [self._get_filter_view_model(f) for f in self.existing_report.prefilters] if self.existing_report else []

    @memoized
    def get_initial_user_filters(self):
        if self.existing_report:
            return [self._get_filter_view_model(f) for f in self.existing_report.filters_without_prefilters]
        if self.source_type == 'case':
            return self._default_case_report_filters
        else:
            # self.source_type == 'form'
            return self._default_form_report_filters

    def _get_filter_view_model(self, filter):
        """
        Given a ReportFilter, return a FilterViewModel representing
        the knockout view model representing this filter in the report builder.

        """
        exists = self._data_source_prop_exists(filter['field'])
        if filter['type'] == 'pre':
            return DefaultFilterViewModel(
                exists_in_current_version=exists,
                display_text='',
                format='Value' if filter['pre_value'] else 'Date',
                property=self._get_property_id_by_indicator_id(filter['field']) if exists else None,
                data_source_field=filter['field'] if not exists else None,
                pre_value=filter['pre_value'],
                pre_operator=filter['pre_operator'],
            )
        else:
            filter_type_map = {
                'dynamic_choice_list': 'Choice',
                # This exists to handle the `closed` filter that might exist
                'choice_list': 'Choice',
                'date': 'Date',
                'numeric': 'Numeric'
            }
            return UserFilterViewModel(
                exists_in_current_version=exists,
                display_text=filter['display'],
                format=filter_type_map[filter['type']],
                property=self._get_property_id_by_indicator_id(filter['field']) if exists else None,
                data_source_field=filter['field'] if not exists else None
            )

    @property
    @memoized
    def _default_case_report_filters(self):
        return [
            UserFilterViewModel(
                exists_in_current_version=True,
                property='closed',
                data_source_field=None,
                display_text=_('Closed'),
                format='Choice',
            ),
            UserFilterViewModel(
                exists_in_current_version=True,
                property='computed/owner_name',
                data_source_field=None,
                display_text=_('Case Owner'),
                format='Choice',
            ),
        ]

    @property
    @memoized
    def _default_form_report_filters(self):
        return [
            UserFilterViewModel(
                exists_in_current_version=True,
                property='timeEnd',
                data_source_field=None,
                display_text='Form completion time',
                format='Date',
            ),
        ]

    def _get_filters(self, report_data):
        """
        Return the dict filter configurations to be used by the
        ReportConfiguration that this form produces.
        """

        def _make_report_filter(conf, index):
            property = self.data_source_builder.data_source_properties[conf["property"]]
            col_id = property.column_id

            selected_filter_type = conf['format']
            if not selected_filter_type or self.source_type == 'form':
                if property.type == 'question':
                    filter_format = get_filter_format_from_question_type(
                        property.source['type']
                    )
                else:
                    assert property.type == 'meta'
                    filter_format = get_filter_format_from_question_type(
                        property.source[1]
                    )
            else:
                filter_format = REPORT_BUILDER_FILTER_TYPE_MAP[selected_filter_type]

            ret = {
                "field": col_id,
                "slug": "{}_{}".format(col_id, index),
                "display": conf["display_text"],
                "type": filter_format
            }
            if conf['format'] == 'Date':
                ret.update({'compare_as_string': True})
            if conf.get('pre_value') or conf.get('pre_operator'):
                ret.update({
                    'type': 'pre',  # type could have been "date"
                    'pre_operator': conf.get('pre_operator', None),
                    'pre_value': conf.get('pre_value', []),
                })
            return ret

        user_filter_configs = report_data['user_filters']
        default_filter_configs = report_data['default_filters']
        filters = [_make_report_filter(f, i) for i, f in enumerate(user_filter_configs + default_filter_configs)]
        if self.source_type == 'case':
            # The UI doesn't support specifying "choice_list" filters, only "dynamic_choice_list" filters.
            # But, we want to make the open/closed filter a cleaner "choice_list" filter, so we do that here.
            self._convert_closed_filter_to_choice_list(filters)
        return filters

    @classmethod
    def _convert_closed_filter_to_choice_list(cls, filters):
        for f in filters:
            if f['field'] == get_column_name('closed') and f['type'] == 'dynamic_choice_list':
                f['type'] = 'choice_list'
                f['choices'] = [
                    {'value': 'True'},
                    {'value': 'False'}
                ]

    def _get_columns(self, report_data):
        return list(chain.from_iterable(
            to_report_columns(c, i, self.report_column_options)
            for i, c in enumerate(report_data['columns'])
        ))

    def _get_report_charts(self, report_data_):
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
        func = report_type_funcs[report_data_['chart']]
        return func(report_data_['columns'])

    def _update_data_source(self, report_data):
        data_source = DataSourceConfiguration.get(self.existing_report.config_id)
        if data_source.get_report_count() > 1:
            # If another report is pointing at this data source, create a new
            # data source for this report so that we can change the indicators
            # without worrying about breaking another report.
            data_source_config_id = self._build_data_source(report_data['columns'])
            self.existing_report.config_id = data_source_config_id
        else:
            number_columns = [c['column_id'] for c in report_data['columns'] if c.get("aggregation" in ['avg', 'sum'])]
            indicators = self.ds_builder.indicators(number_columns)
            if data_source.configured_indicators != indicators:
                for property_name, value in self._get_data_source_configuration_kwargs(
                    report_data['columns']
                ).iteritems():
                    setattr(data_source, property_name, value)
                data_source.save()
                rebuild_indicators.delay(data_source._id)

    def _update_report(self, report_data):
        self._update_data_source(report_data)
        self.existing_report.title = report_data['report_title'] or self.existing_report.title
        self.existing_report.description = report_data['report_description'] or self.existing_report.description
        self.existing_report.aggregation_columns = self._get_aggregation_columns(report_data)
        self.existing_report.columns = self._get_columns(report_data)
        self.existing_report.filters = self._get_filters(report_data)
        self.existing_report.configured_charts = self._get_report_charts(report_data)

        self.existing_report.validate()
        self.existing_report.save()

    def _get_data_source_configuration_kwargs(self, columns, is_multiselect_chart_report=False):
        aggregation_fields = [c['column_id'] for c in columns if c['is_group_by_column']]
        if is_multiselect_chart_report:
            base_item_expression = self.ds_builder.base_item_expression(True, aggregation_fields[0])
        else:
            base_item_expression = self.ds_builder.base_item_expression(False)
        number_columns = [c['column_id'] for c in columns if c.get("aggregation" in ['avg', 'sum'])]
        return dict(
            display_name=self.ds_builder.data_source_name,
            referenced_doc_type=self.ds_builder.source_doc_type,
            configured_filter=self.ds_builder.filter,
            configured_indicators=self.ds_builder.indicators(
                number_columns, is_multiselect_chart_report
            ),
            base_item_expression=base_item_expression,
            meta=DataSourceMeta(build=DataSourceBuildInformation(
                source_id=self.source_id,
                app_id=self.app._id,
                app_version=self.app.version,
            ))
        )

    @property
    @memoized
    def ds_builder(self):
        return DataSourceBuilder(self.domain, self.app, self.source_type, self.source_id)

    def _build_data_source(self, columns):

        def build_data_source(domain_, ds_config_kwargs_):
            data_source_config = DataSourceConfiguration(
                domain=domain_,
                # The uuid gets truncated, so it's not really universally unique.
                table_id=_clean_table_name(domain_, str(uuid.uuid4().hex)),
                **ds_config_kwargs_
            )
            data_source_config.validate()
            data_source_config.save()
            rebuild_indicators.delay(data_source_config._id)
            return data_source_config._id

        ds_config_kwargs = self._get_data_source_configuration_kwargs(columns)
        # TODO: Don't build new data source if there is an existing one
        return build_data_source(self.domain, ds_config_kwargs)

    def post(self, request, domain, *args, **kwargs):

        def get_builder_report_type(report_data_):
            # builder_report_type = StringProperty(choices=['chart', 'list', 'table', 'worker', 'map'])
            assert report_data_['report_type'] in ('list', 'agg', 'map')
            if report_data_['report_type'] in ('list', 'map'):
                return report_data_['report_type']
            elif report_data_['report_type'] == 'agg':
                return 'table' if report_data_['chart'] == 'none' else 'chart'

        report_data = json.loads(request.body)
        if report_data['existing_report'] and not self.existing_report:
            # This is the case if the user has clicked "Save" for a second time from the new report page
            # i.e. the user created a report with the first click, but didn't navigate to the report view page
            self.existing_report = ReportConfiguration.get(report_data['existing_report'])

        try:
            if self.existing_report:
                self._update_report(report_data)
                report_configuration = self.existing_report
            else:
                self._confirm_report_limit()
                # TODO: Don't build new data source if there is an existing one
                data_source_config_id = self._build_data_source(report_data['columns'])
                self._confirm_report_limit()

                report_configuration = ReportConfiguration(
                    domain=self.domain,
                    config_id=data_source_config_id,
                    title=report_data['report_title'],
                    description=report_data['report_description'],
                    aggregation_columns=self._get_aggregation_columns(report_data),
                    columns=self._get_columns(report_data),
                    filters=self._get_filters(report_data),
                    configured_charts=self._get_report_charts(report_data),
                    report_meta=ReportMeta(
                        created_by_builder=True,
                        builder_report_type=get_builder_report_type(report_data),
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
        return json_response(
            {
                'report_url': reverse(ConfigurableReport.slug, args=[self.domain, report_configuration._id]),
                'report_id': report_configuration._id,
            }
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


def _get_multiselect_indicator_id(column_field, indicators):
    """
    If this column_field corresponds to a multiselect data source indicator, then return the id of the
    indicator. Otherwise return None.
    :param column_field: The "field" property of a report column
    :return: a data source indicator id
    """
    # TODO: Remove this from the form where I coppied it
    indicator_id = "_".join(column_field.split("_")[:-1])
    for indicator in indicators:
        if indicator['column_id'] == indicator_id and indicator['type'] == 'choice_list':
            return indicator_id
    return None


class ReportPreview(BaseDomainView):
    urlname = 'report_preview'

    def post(self, request, domain, data_source):
        report_data = json.loads(urllib.unquote(request.body))
        column_options = _report_column_options(
            self.domain, Application.get(report_data['app']), report_data['source_type'], report_data['source_id']
        )

        table = ConfigurableReport.report_config_table(
            domain=domain,
            config_id=data_source,
            title='{}_{}_{}'.format(TEMP_REPORT_PREFIX, domain, data_source),
            description='',
            aggregation_columns=_get_aggregation_columns(
                report_data['aggregate'], report_data['columns'], column_options
            ),
            columns=list(chain.from_iterable(
                to_report_columns(c, i, column_options) for i, c in enumerate(report_data['columns'])
            )),
            report_meta=ReportMeta(created_by_builder=True),
        )  # is None if report configuration doesn't make sense or data source has expired
        if table:
            return json_response(table[0][1])
        else:
            return json_response({'status': 'error', 'message': 'Invalid report configuration'}, status_code=400)


class ConfigureMapReport(ConfigureReport):
    urlname = 'configure_map_report'
    report_title = ugettext_lazy("Map Report: {}")
    report_type = 'map'


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


class ExpressionDebuggerView(BaseUserConfigReportsView):
    urlname = 'expression_debugger'
    template_name = 'userreports/expression_debugger.html'
    page_title = ugettext_lazy("Expression Debugger")


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def evaluate_expression(request, domain):
    doc_type = request.POST['doc_type']
    doc_id = request.POST['doc_id']
    try:
        usable_type = {
            'form': 'XFormInstance',
            'case': 'CommCareCase',
        }.get(doc_type, 'Unknown')
        document_store = get_document_store(domain, usable_type)
        doc = document_store.get_document(doc_id)
        expression_text = request.POST['expression']
        expression_json = json.loads(expression_text)
        parsed_expression = ExpressionFactory.from_spec(expression_json)
        result = parsed_expression(doc, EvaluationContext(doc))
        return json_response({
            "result": result,
        })
    except DocumentNotFoundError:
        return json_response(
            {"error": _("{} with id {} not found in domain {}.").format(
                doc_type, doc_id, domain
            )},
            status_code=404,
        )
    except BadSpecError as e:
        return json_response(
            {"error": _("Problem with expression: {}.").format(
                e
            )},
            status_code=400,
        )
    except Exception as e:
        return json_response(
            {"error": unicode(e)},
            status_code=500,
        )


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
        return u"Edit {}".format(self.config.display_name)


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
