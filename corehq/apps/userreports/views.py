from __future__ import absolute_import
from __future__ import unicode_literals
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
from collections import namedtuple, OrderedDict
import datetime
import functools
import json
import os
import tempfile
import re

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse
from django.http.response import Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import View

from couchdbkit.exceptions import ResourceNotFound
from sqlalchemy import types, exc
from sqlalchemy.exc import ProgrammingError

from corehq.apps.accounting.models import Subscription
from corehq.apps.analytics.tasks import update_hubspot_properties, send_hubspot_form, HUBSPOT_SAVED_UCR_FORM_ID
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.reports.daterange import get_simple_dateranges
from corehq.apps.userreports.dbaccessors import get_datasources_for_domain
from corehq.apps.userreports.app_manager.data_source_meta import DATA_SOURCE_TYPE_RAW
from corehq.apps.userreports.reports.builder.sources import get_source_type_from_report_config
from corehq.apps.userreports.specs import FactoryContext
from corehq.apps.userreports.indicators.factory import IndicatorFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.tabs.tabclasses import ProjectReportsTab
from corehq.util import reverse
from corehq.util.quickcache import quickcache
from couchexport.export import export_from_tables
from couchexport.files import Temp
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.couch.undo import get_deleted_doc_type, is_deleted, undo_delete, soft_delete
from memoized import memoized
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import purge_report_from_mobile_ucr
from corehq.apps.domain.decorators import login_and_domain_required, api_auth
from corehq.apps.locations.permissions import conditionally_location_safe
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.reports.dispatcher import cls_to_view_login_and_domain
from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.hqwebapp.decorators import (
    use_daterangepicker,
    use_datatables,
    use_jquery_ui,
    use_nvd3,
)
from corehq.apps.userreports.app_manager.helpers import get_case_data_source, get_form_data_source
from corehq.apps.userreports.const import (
    REPORT_BUILDER_EVENTS_KEY,
    DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE,
    NAMED_EXPRESSION_PREFIX,
    NAMED_FILTER_PREFIX,
    DATA_SOURCE_MISSING_APP_ERROR_MESSAGE)
from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
from corehq.apps.userreports.exceptions import (
    BadBuilderConfigError,
    BadSpecError,
    DataSourceConfigurationNotFoundError,
    ReportConfigurationNotFoundError,
    UserQueryError,
    translate_programming_error, TableNotFoundWarning)
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
)
from corehq.apps.userreports.rebuild import DataSourceResumeHelper
from corehq.apps.userreports.reports.builder.forms import (
    DataSourceForm,
    ConfigureMapReportForm,
    ConfigureListReportForm,
    ConfigureTableReportForm,
    get_data_source_interface)
from corehq.apps.userreports.reports.filters.choice_providers import (
    ChoiceQueryContext,
)
from corehq.apps.userreports.reports.view import ConfigurableReportView
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.tasks import (
    rebuild_indicators,
    resume_building_indicators,
    rebuild_indicators_in_place,
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
from corehq.util.soft_assert import soft_assert
from pillowtop.dao.exceptions import DocumentNotFoundError
import six


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


@method_decorator(toggles.USER_CONFIGURABLE_REPORTS.required_decorator(), name='dispatch')
class BaseUserConfigReportsView(BaseDomainView):
    section_name = ugettext_lazy("Configurable Reports")

    @property
    def main_context(self):
        static_reports = list(StaticReportConfiguration.by_domain(self.domain))
        context = super(BaseUserConfigReportsView, self).main_context
        context.update({
            'reports': ReportConfiguration.by_domain(self.domain) + static_reports,
            'data_sources': get_datasources_for_domain(self.domain, include_static=True)
        })
        if toggle_enabled(self.request, toggles.AGGREGATE_UCRS):
            from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
            context['aggregate_data_sources'] = AggregateTableDefinition.objects.filter(domain=self.domain)
        return context

    @property
    def section_url(self):
        return reverse(UserConfigReportsHomeView.urlname, args=(self.domain,))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))


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
            'referring_apps': self.get_referring_apps(),
        }

    def get_referring_apps(self):
        to_ret = []
        apps = get_apps_in_domain(self.domain)
        for app in apps:
            app_url = reverse('view_app', args=[self.domain, app.id])
            for module in app.get_report_modules():
                module_url = reverse('view_module', args=[self.domain, app.id, module.unique_id])
                for config in module.report_configs:
                    if config.report_id == self.report_id:
                        to_ret.append({
                            "app_url": app_url,
                            "app_name": app.name,
                            "module_url": module_url,
                            "module_name": module.default_name()
                        })
        return to_ret

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
            messages.success(request, _('Report "{}" saved!').format(self.config.title))
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
    @use_daterangepicker
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        return super(ReportBuilderView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        main_context = super(ReportBuilderView, self).main_context
        allowed_num_reports = allowed_report_builder_reports(self.request)
        main_context.update({
            'has_report_builder_access': has_report_builder_access(self.request),
            'at_report_limit': number_of_report_builder_reports(self.domain) >= allowed_num_reports,
            'report_limit': allowed_num_reports,
            'paywall_url': paywall_home(self.domain),
            'pricing_page_url': settings.PRICING_PAGE_URL,
            'support_email': settings.SUPPORT_EMAIL,
        })
        return main_context

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
    domain_obj = Domain.get_by_name(domain, strict=True)
    if domain_obj.requested_report_builder_subscription:
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
        return Subscription.get_subscribed_plan_by_domain(self.domain).plan.name


class ReportBuilderPaywallPricing(ReportBuilderPaywallBase):
    template_name = "userreports/paywall/pricing.html"
    urlname = 'report_builder_paywall_pricing'
    page_title = ugettext_lazy('Pricing')

    @property
    def page_context(self):
        context = super(ReportBuilderPaywallPricing, self).page_context
        max_allowed_reports = allowed_report_builder_reports(self.request)
        num_builder_reports = number_of_report_builder_reports(self.domain)
        context.update({
            'has_report_builder_access': has_report_builder_access(self.request),
            'at_report_limit': num_builder_reports >= max_allowed_reports,
            'max_allowed_reports': max_allowed_reports,
            'support_email': settings.SUPPORT_EMAIL,
            'pricing_page_url': settings.PRICING_PAGE_URL,
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

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            app_source = self.form.get_selected_source()

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
                messages.error(request, six.text_type(e))
                return HttpResponseRedirect(reverse(ConfigurableReportView.slug, args=[request.domain, report_id]))
        raise Http404("Report was not created by the report builder")


class ConfigureReport(ReportBuilderView):
    urlname = 'configure_report'
    page_title = ugettext_lazy("Configure Report")
    template_name = "userreports/reportbuilder/configure_report.html"
    report_title = '{}'
    existing_report = None

    @use_jquery_ui
    @use_datatables
    @use_nvd3
    def dispatch(self, request, *args, **kwargs):
        if self.existing_report:
            self.source_type = get_source_type_from_report_config(self.existing_report)
            if self.source_type != DATA_SOURCE_TYPE_RAW:
                self.source_id = self.existing_report.config.meta.build.source_id
                self.app_id = self.existing_report.config.meta.build.app_id
                self.app = Application.get(self.app_id) if self.app_id else None
            else:
                self.source_id = self.existing_report.config_id
                self.app_id = self.app = None
        else:
            self.app_id = self.request.GET['application']
            self.app = Application.get(self.app_id)
            self.source_type = self.request.GET['source_type']
            self.source_id = self.request.GET['source']

        if not self.app_id and self.source_type != DATA_SOURCE_TYPE_RAW:
            raise BadBuilderConfigError(DATA_SOURCE_MISSING_APP_ERROR_MESSAGE)
        try:
            data_source_interface = get_data_source_interface(
                self.domain, self.app, self.source_type, self.source_id
            )
        except ResourceNotFound:
            self.template_name = 'userreports/report_error.html'
            if self.existing_report:
                context = {'report_id': self.existing_report.get_id,
                           'is_static': self.existing_report.is_static}
            else:
                context = {}
            context['error_message'] = DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE
            context.update(self.main_context)
            return self.render_to_response(context)

        self._populate_data_source_properties_from_interface(data_source_interface)
        return super(ConfigureReport, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        title = self._get_report_name()
        return _(self.report_title).format(title)

    @property
    def report_description(self):
        if self.existing_report:
            return self.existing_report.description or None
        return None

    def _populate_data_source_properties_from_interface(self, data_source_interface):
        self._properties_by_column_id = {}
        for p in data_source_interface.data_source_properties.values():
            column = p.to_report_column_option()
            for agg in column.aggregation_options:
                indicators = column.get_indicators(agg)
                for i in indicators:
                    self._properties_by_column_id[i['column_id']] = p

    def _get_report_name(self, request=None):
        if self.existing_report:
            return self.existing_report.title
        else:
            request = request or self.request
            return request.GET.get('report_name', '')

    def _get_existing_report_type(self):
        if self.existing_report:
            type_ = "list"
            if self.existing_report.aggregation_columns != ["doc_id"]:
                type_ = "table"
            if self.existing_report.map_config:
                type_ = "map"
            return type_

    def _get_property_id_by_indicator_id(self, indicator_column_id):
        """
        Return the data source property id corresponding to the given data
        source indicator column id.
        :param indicator_column_id: The column_id field of a data source indicator
            configuration dictionary
        :return: A DataSourceProperty property id, e.g. "/data/question1"
        """
        data_source_property = self._properties_by_column_id.get(indicator_column_id)
        if data_source_property:
            return data_source_property.get_id()

    def _get_initial_location(self, report_form):
        if self.existing_report:
            cols = [col for col in self.existing_report.report_columns if col.type == 'location']
            if cols:
                indicator_id = cols[0].field
                return report_form._get_property_id_by_indicator_id(indicator_id)

    def _get_initial_chart_type(self):
        if self.existing_report:
            if self.existing_report.configured_charts:
                type_ = self.existing_report.configured_charts[0]['type']
                if type_ == "multibar":
                    return "bar"
                if type_ == "pie":
                    return "pie"

    def _get_column_options(self, report_form):
        options = OrderedDict()
        for option in report_form.report_column_options.values():
            key = option.get_uniquenss_key()
            if key in options:
                options[key].append(option)
            else:
                options[key] = [option]

    @property
    def page_context(self):
        form_type = _get_form_type(self._get_existing_report_type())
        report_form = form_type(
            self.domain, self.page_name, self.app_id, self.source_type, self.source_id, self.existing_report
        )
        temp_ds_id = report_form.create_temp_data_source_if_necessary(self.request.user.username)

        return {
            'existing_report': self.existing_report,
            'report_description': self.report_description,
            'report_title': self.page_name,
            'existing_report_type': self._get_existing_report_type(),

            'column_options': [p.to_view_model() for p in report_form.report_column_options.values()],
            # TODO: Consider renaming this because it's more like "possible" data source props
            'data_source_properties': [p.to_view_model() for p in report_form.data_source_properties.values()],
            'initial_user_filters': [f._asdict() for f in report_form.initial_user_filters],
            'initial_default_filters': [f._asdict() for f in report_form.initial_default_filters],
            'initial_columns': [c._asdict() for c in report_form.initial_columns],
            'initial_location': self._get_initial_location(report_form),
            'initial_chart_type': self._get_initial_chart_type(),
            'source_type': self.source_type,
            'source_id': self.source_id,
            'application': self.app_id,
            'report_preview_url': reverse(ReportPreview.urlname,
                                          args=[self.domain, temp_ds_id]),
            'preview_datasource_id': temp_ds_id,
            'report_builder_events': self.request.session.pop(REPORT_BUILDER_EVENTS_KEY, []),
            'MAPBOX_ACCESS_TOKEN': settings.MAPBOX_ACCESS_TOKEN,
            'date_range_options': [r._asdict() for r in get_simple_dateranges()],
        }

    def _get_bound_form(self, report_data):
        form_class = _get_form_type(report_data['report_type'])
        return form_class(
            self.domain,
            self._get_report_name(),
            self.app._id,
            self.source_type,
            self.source_id,
            self.existing_report,
            report_data
        )

    def post(self, request, domain, *args, **kwargs):
        if not has_report_builder_access(request):
            raise Http404

        report_data = json.loads(request.body.decode('utf-8'))
        if report_data['existing_report'] and not self.existing_report:
            # This is the case if the user has clicked "Save" for a second time from the new report page
            # i.e. the user created a report with the first click, but didn't navigate to the report view page
            self.existing_report = ReportConfiguration.get(report_data['existing_report'])

        _munge_report_data(report_data)

        bound_form = self._get_bound_form(report_data)

        if bound_form.is_valid():
            if self.existing_report:
                report_configuration = bound_form.update_report()
            else:
                self._confirm_report_limit()
                try:
                    report_configuration = bound_form.create_report()
                except BadSpecError as err:
                    messages.error(self.request, str(err))
                    notify_exception(self.request, str(err), details={
                        'domain': self.domain,
                        'report_form_class': bound_form.__class__.__name__,
                        'report_type': bound_form.report_type,
                        'group_by': getattr(bound_form, 'group_by', 'Not set'),
                        'user_filters': getattr(bound_form, 'user_filters', 'Not set'),
                        'default_filters': getattr(bound_form, 'default_filters', 'Not set'),
                    })
                    return self.get(request, domain, *args, **kwargs)
                else:
                    ProjectReportsTab.clear_dropdown_cache(domain, request.couch_user.get_id)
            self._delete_temp_data_source(report_data)
            send_hubspot_form(HUBSPOT_SAVED_UCR_FORM_ID, request)
            return json_response({
                'report_url': reverse(ConfigurableReportView.slug, args=[self.domain, report_configuration._id]),
                'report_id': report_configuration._id,
            })

    def _delete_temp_data_source(self, report_data):
        if report_data.get("delete_temp_data_source", False):
            delete_data_source_shared(self.domain, report_data["preview_data_source_id"])

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


def update_report_description(request, domain, report_id):
    new_description = request.POST['value']
    report = get_document_or_404(ReportConfiguration, domain, report_id)
    report.description = new_description
    report.save()
    return json_response({})


def _get_form_type(report_type):
    assert report_type in (None, "list", "table", "chart", "map")
    if report_type == "list" or report_type is None:
        return ConfigureListReportForm
    if report_type == "table":
            return ConfigureTableReportForm
    if report_type == "map":
        return ConfigureMapReportForm


def _munge_report_data(report_data):
    """
    Split aggregation columns out of report_data and into
    :param report_data:
    :return:
    """
    report_data['columns'] = json.dumps(report_data['columns'])
    report_data['user_filters'] = json.dumps(report_data['user_filters'])
    report_data['default_filters'] = json.dumps(report_data['default_filters'])


class ReportPreview(BaseDomainView):
    urlname = 'report_preview'

    def post(self, request, domain, data_source):
        report_data = json.loads(six.moves.urllib.parse.unquote(request.body.decode('utf-8')))
        form_class = _get_form_type(report_data['report_type'])

        # ignore user filters
        report_data['user_filters'] = []

        _munge_report_data(report_data)
        bound_form = form_class(
            domain,
            '{}_{}_{}'.format(TEMP_REPORT_PREFIX, self.domain, data_source),
            report_data['app'],
            report_data['source_type'],
            report_data['source_id'],
            None,
            report_data
        )
        if bound_form.is_valid():
            try:
                temp_report = bound_form.create_temp_report(data_source, self.request.user.username)
                response_data = ConfigurableReportView.report_preview_data(self.domain, temp_report)
                if response_data:
                    return json_response(response_data)
            except BadBuilderConfigError as e:
                return json_response({'status': 'error', 'message': str(e)}, status_code=400)

        return json_response({'status': 'error', 'message': 'Invalid report configuration'}, status_code=400)


def _assert_report_delete_privileges(request):
    if not (toggle_enabled(request, toggles.USER_CONFIGURABLE_REPORTS)
            or toggle_enabled(request, toggles.REPORT_BUILDER)
            or toggle_enabled(request, toggles.REPORT_BUILDER_BETA_GROUP)
            or has_report_builder_add_on_privilege(request)):
        raise Http404()


def delete_report(request, domain, report_id):
    _assert_report_delete_privileges(request)
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
            data_source.deactivate(initiated_by=request.user.username)

    soft_delete(config)
    did_purge_something = purge_report_from_mobile_ucr(config)

    messages.success(
        request,
        _('Report "{name}" has been deleted. <a href="{url}" class="post-link">Undo</a>').format(
            name=config.title,
            url=reverse('undo_delete_configurable_report', args=[domain, config._id]),
        ),
        extra_tags='html'
    )

    report_configs = ReportConfig.by_domain_and_owner(
        domain, request.couch_user.get_id, "configurable")
    for rc in report_configs:
        if rc.subreport_slug == config.get_id:
            rc.delete()

    if did_purge_something:
        messages.warning(
            request,
            _("This report was used in one or more applications. "
              "It has been removed from there too.")
        )
    ProjectReportsTab.clear_dropdown_cache(domain, request.couch_user.get_id)
    redirect = request.GET.get("redirect", None)
    if not redirect:
        redirect = reverse('configurable_reports_home', args=[domain])
    return HttpResponseRedirect(redirect)


def undelete_report(request, domain, report_id):
    _assert_report_delete_privileges(request)
    config = get_document_or_404(ReportConfiguration, domain, report_id, additional_doc_types=[
        get_deleted_doc_type(ReportConfiguration)
    ])
    if config and is_deleted(config):
        undo_delete(config)
        messages.success(
            request,
            _('Successfully restored report "{name}"').format(name=config.title)
        )
    else:
        messages.info(request, _('Report "{name}" not deleted.').format(name=config.title))
    return HttpResponseRedirect(reverse(ConfigurableReportView.slug, args=[request.domain, report_id]))


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


class DataSourceDebuggerView(BaseUserConfigReportsView):
    urlname = 'expression_debugger'
    template_name = 'userreports/data_source_debugger.html'
    page_title = ugettext_lazy("Data Source Debugger")


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def evaluate_expression(request, domain):
    doc_type = request.POST['doc_type']
    doc_id = request.POST['doc_id']
    data_source_id = request.POST['data_source']
    try:
        if data_source_id:
            data_source = get_datasource_config(data_source_id, domain)[0]
            factory_context = data_source.get_factory_context()
        else:
            factory_context = FactoryContext.empty()
        usable_type = {
            'form': 'XFormInstance',
            'case': 'CommCareCase',
        }.get(doc_type, 'Unknown')
        document_store = get_document_store_for_doc_type(
            domain, usable_type, load_source="eval_expression")
        doc = document_store.get_document(doc_id)
        expression_text = request.POST['expression']
        expression_json = json.loads(expression_text)
        parsed_expression = ExpressionFactory.from_spec(
            expression_json,
            context=factory_context
        )
        result = parsed_expression(doc, EvaluationContext(doc))
        return json_response({
            "result": result,
        })
    except DataSourceConfigurationNotFoundError:
        return json_response(
            {"error": _("Data source with id {} not found in domain {}.").format(
                data_source_id, domain
            )},
            status_code=404,
        )
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
            {"error": six.text_type(e)},
            status_code=500,
        )


@login_and_domain_required
@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
def evaluate_data_source(request, domain):
    data_source_id = request.POST['data_source']
    docs_id = request.POST['docs_id']
    try:
        data_source = get_datasource_config(data_source_id, domain)[0]
    except DataSourceConfigurationNotFoundError:
        return JsonResponse(
            {"error": _("Data source with id {} not found in domain {}.").format(
                data_source_id, domain
            )},
            status=404,
        )

    docs_id = [doc_id.strip() for doc_id in docs_id.split(',')]
    document_store = get_document_store_for_doc_type(
        domain, data_source.referenced_doc_type, load_source="eval_data_source")
    rows = []
    docs = 0
    for doc in document_store.iter_documents(docs_id):
        docs += 1
        for row in data_source.get_all_values(doc):
            rows.append({i.column.database_column_name.decode(): i.value for i in row})

    if not docs:
        return JsonResponse(data={'error': _('No documents found. Check the IDs and try again.')}, status=404)

    data = {
        'rows': rows,
        'db_rows': [],
        'columns': [
            column.database_column_name.decode() for column in data_source.get_columns()
        ],
    }

    try:
        adapter = get_indicator_adapter(data_source)
        table = adapter.get_table()
        query = adapter.get_query_object().filter(table.c.doc_id.in_(docs_id))
        db_rows = [
            {column.name: getattr(row, column.name) for column in table.columns}
            for row in query
        ]
        data['db_rows'] = db_rows
    except ProgrammingError as e:
        err = translate_programming_error(e)
        if err and isinstance(err, TableNotFoundWarning):
            data['db_error'] = _("Datasource table does not exist. Try rebuilding the datasource.")
        else:
            data['db_error'] = _("Error querying database for data.")

    return JsonResponse(data=data)


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
                messages.success(request, _("Data source created for '{}'".format(app_source.source)))
            else:
                assert app_source.source_type == 'form'
                xform = app.get_form(app_source.source)
                data_source = get_form_data_source(app, xform)
                data_source.save()
                messages.success(request, _("Data source created for '{}'".format(xform.default_name())))

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
            'used_by_reports': self.get_reports(),
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
            messages.success(request, _('Data source "{}" saved!').format(
                config.display_name
            ))
            if self.config_id is None:
                return HttpResponseRedirect(reverse(
                    EditDataSourceView.urlname, args=[self.domain, config._id])
                )
        return self.get(request, *args, **kwargs)

    def get_reports(self):
        reports = StaticReportConfiguration.by_domain(self.domain)
        reports += ReportConfiguration.by_domain(self.domain)
        ret = []
        for report in reports:
            try:
                if report.table_id == self.config.table_id:
                    ret.append(report)
            except DataSourceConfigurationNotFoundError:
                _soft_assert = soft_assert(to=[
                    '{}@{}'.format(name, 'dimagi.com')
                    for name in ['jemord', 'cellowitz', 'npellegrino', 'frener']
                ])
                _soft_assert(False, "Report {} on domain {} attempted to reference deleted table".format(
                    report._id, self.domain
                ))
        return ret

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
    username = request.user.username if request else None
    skip = not request  # skip logging when we remove temporary tables
    adapter.drop_table(initiated_by=username, source='delete_data_source', skip_log=skip)
    soft_delete(config)
    if request:
        messages.success(
            request,
            _('Data source "{name}" has been deleted. <a href="{url}" class="post-link">Undo</a>').format(
                name=config.display_name,
                url=reverse('undo_delete_data_source', args=[domain, config._id]),
            ),
            extra_tags='html'
        )


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
@require_POST
def undelete_data_source(request, domain, config_id):
    config = get_document_or_404(DataSourceConfiguration, domain, config_id, additional_doc_types=[
        get_deleted_doc_type(DataSourceConfiguration)
    ])
    if config and is_deleted(config):
        undo_delete(config)
        messages.success(
            request,
            _('Successfully restored data source "{name}"').format(name=config.display_name)
        )
    else:
        messages.info(request, _('Data source "{name}" not deleted.').format(name=config.display_name))
    return HttpResponseRedirect(reverse(
        EditDataSourceView.urlname, args=[domain, config._id]
    ))


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
            _('Table "{}" has already finished building. Rebuild table to start over.').format(
                config.display_name
            )
        )
    elif not DataSourceResumeHelper(config).has_resume_info():
        messages.warning(
            request,
            _('Table "{}" did not finish building but resume information is not available. '
              'Unfortunately, this means you need to rebuild the table.').format(
                config.display_name
            )
        )
    else:
        messages.success(
            request,
            _('Resuming rebuilding table "{}".').format(config.display_name)
        )
        resume_building_indicators.delay(config_id, request.user.username)
    return HttpResponseRedirect(reverse(
        EditDataSourceView.urlname, args=[domain, config._id]
    ))


@toggles.USER_CONFIGURABLE_REPORTS.required_decorator()
@require_POST
def build_data_source_in_place(request, domain, config_id):
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

    rebuild_indicators_in_place.delay(config_id, request.user.username, source='edit_data_source_build_in_place')
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
            'data': [list(row) for row in q[:20]],
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


@api_auth
@require_permission(Permissions.view_reports)
@swallow_programming_errors
def export_data_source(request, domain, config_id):
    config, _ = get_datasource_config_or_404(config_id, domain)
    adapter = get_indicator_adapter(config, load_source='export_data_source')
    url = reverse('export_configurable_data_source', args=[domain, config._id])
    return export_sql_adapter_view(request, domain, adapter, url)


def export_sql_adapter_view(request, domain, adapter, too_large_redirect_url):
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
        return HttpResponse(six.text_type(e), status=400)

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
                too_large_redirect_url,
                urlencode(keyword_params)
            )
        )

    # build export
    def get_table(q):
        yield list(table.columns.keys())
        for row in q:
            adapter.track_load()
            yield row

    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as tmpfile:
        try:
            tables = [[adapter.table_id, get_table(q)]]
            export_from_tables(tables, tmpfile, params.format)
        except exc.DataError:
            msg = ugettext_lazy(
                "There was a problem executing your query, "
                "please make sure your parameters are valid."
            )
            return HttpResponse(msg, status=400)
        return export_response(Temp(path), params.format, adapter.display_name)


@login_and_domain_required
def data_source_status(request, domain, config_id):
    config, _ = get_datasource_config_or_404(config_id, domain)
    build = config.meta.build
    # there appears to be a way that these can be built, but not have initiated set
    if build.initiated or build.initiated_in_place:
        return JsonResponse({
            'isBuilt': build.finished or build.rebuilt_asynchronously or build.finished_in_place
        })

    return JsonResponse({'isBuilt': True})


def _get_report_filter(domain, report_id, filter_id):
    report = get_report_config_or_404(report_id, domain)[0]
    report_filter = report.get_ui_filter(filter_id)
    if report_filter is None:
        raise Http404(_('Filter {} not found!').format(filter_id))
    return report_filter


def _is_location_safe_choice_list(view_fn, request, domain, report_id, filter_id, **view_kwargs):
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


class DataSourceSummaryView(BaseUserConfigReportsView):
    urlname = 'summary_configurable_data_source'
    template_name = "userreports/summary_data_source.html"
    page_title = ugettext_lazy("Data Source Summary")

    @property
    def config_id(self):
        return self.kwargs['config_id']

    @property
    @memoized
    def config(self):
        return get_datasource_config_or_404(self.config_id, self.domain)[0]

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.config_id,))

    @property
    def page_name(self):
        return "Summary - {}".format(self.config.display_name)

    @property
    def page_context(self):
        return {
            'datasource_display_name': self.config.display_name,
            'filter_summary': self.configured_filter_summary(),
            'indicator_summary': self._add_links_to_output(self.indicator_summary()),
            'named_expression_summary': self._add_links_to_output(self.named_expression_summary()),
            'named_filter_summary': self._add_links_to_output(self.named_filter_summary()),
            'named_filter_prefix': NAMED_FILTER_PREFIX,
            'named_expression_prefix': NAMED_EXPRESSION_PREFIX,
        }

    def indicator_summary(self):
        context = self.config.get_factory_context()
        wrapped_specs = [
            IndicatorFactory.from_spec(spec, context).wrapped_spec
            for spec in self.config.configured_indicators
        ]
        return [
            {
                "column_id": wrapped.column_id,
                "comment": wrapped.comment,
                "readable_output": wrapped.readable_output(context)
            }
            for wrapped in wrapped_specs if wrapped
        ]

    def named_expression_summary(self):
        return [
            {
                "name": name,
                "comment": self.config.named_expressions[name].get('comment'),
                "readable_output": str(exp)
            }
            for name, exp in self.config.named_expression_objects.items()
        ]

    def named_filter_summary(self):
        return [
            {
                "name": name,
                "comment": self.config.named_filters[name].get('comment'),
                "readable_output": str(filter)
            }
            for name, filter in self.config.named_filter_objects.items()
        ]

    def configured_filter_summary(self):
        return str(FilterFactory.from_spec(self.config.configured_filter,
                                           context=self.config.get_factory_context()))

    def _add_links_to_output(self, items):
        def make_link(match):
            value = match.group()
            return '<a href="#{value}">{value}</a>'.format(value=value)

        def add_links(content):
            content = re.sub(r"{}:[A-Za-z0-9_-]+".format(NAMED_FILTER_PREFIX), make_link, content)
            content = re.sub(r"{}:[A-Za-z0-9_-]+".format(NAMED_EXPRESSION_PREFIX), make_link, content)
            return content

        list = []
        for i in items:
            i['readable_output'] = add_links(i.get('readable_output'))
            list.append(i)
        return list
