from functools import cached_property

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET

from memoized import memoized

from dimagi.utils.web import json_request

from corehq import toggles
from corehq.apps.data_dictionary.util import get_gps_properties
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.es.case_search import CaseSearchES, case_property_missing
from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY
from corehq.apps.geospatial.utils import get_lat_lon_from_dict
from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.reports.generic import get_filter_classes
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.views import BaseProjectReportSectionView
from corehq.apps.userreports.reports.view import ConfigurableReportView
from corehq.form_processor.models import CommCareCase
from corehq.util.htmx_action import (
    HqHtmxActionMixin,
    HtmxResponseException,
    hq_hx_action,
)
from corehq.util.timezones.utils import get_timezone

from .const import GAUGE_METRICS
from .models import Dashboard, WidgetType
from .services import get_gauge_metric_value


class DashboardMapFilterMixin(object):
    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
    ]

    def dashboard_map_case_filters_context(self):
        return {
            'report': {
                'title': self.page_title,
                'section_name': self.section_name,
                'show_filters': True,
            },
            'report_filters': [
                dict(field=f.render(), slug=f.slug) for f in self.dashboard_map_filter_classes
            ],
            'report_filter_form_action_css_class': CSS_ACTION_CLASS,
        }

    @property
    @memoized
    def dashboard_map_filter_classes(self):
        timezone = get_timezone(self.request, self.domain)
        return get_filter_classes(self.fields, self.request, self.domain, timezone)


class DashboardReportMixin:

    def dashboard_reports_context(self):
        # TODO: Add context for each report
        # context_by_id = {}
        # for report in self.dashboard.reports.all():
        #     view = self._get_configurable_report_view(report)
        #     context_by_id[report.id] = view.page_context
        # return {'context_by_id': context_by_id}
        report = self.dashboard.reports.first()
        if report:
            view = self._get_dashboard_report_view(report)
            return view.page_context
        return {}

    def _get_dashboard_report_view(self, report):
        view = DashboardReportView()
        view.request = self.request
        view._domain = self.domain
        view.args = []
        view.kwargs = {
            'domain': self.domain,
            'slug': DashboardReportView.slug,
            'subreport_slug': report.report_configuration_id,
        }
        return view


@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.CAMPAIGN_DASHBOARD.required_decorator(), name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class DashboardView(
    BaseProjectReportSectionView,
    DashboardMapFilterMixin,
    DashboardReportMixin,
):
    urlname = 'campaign_dashboard'
    page_title = gettext_lazy("Campaign Dashboard")
    template_name = 'campaign/dashboard.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    @memoized
    def dashboard(self):
        """
        Returns the campaign dashboard for the domain. Creates an empty
        one if it doesn't exist yet.
        """
        dashboard, __ = Dashboard.objects.get_or_create(domain=self.domain)
        return dashboard

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
            'map_report_widgets': self.dashboard.get_map_report_widgets_by_tab(),
            'gauge_widgets': self._dashboard_gauge_configs(),
            'widget_types': WidgetType.choices,
        })
        context.update(self.dashboard_map_case_filters_context())
        context.update(self.dashboard_reports_context())
        return context

    def _dashboard_gauge_configs(self):
        dashboard_gauge_configs = {
            'cases': [],
            'mobile_workers': [],
        }
        for dashboard_gauge in self.dashboard.gauges.all():
            dashboard_gauge_configs[dashboard_gauge.dashboard_tab].append(
                self._get_gauge_config(dashboard_gauge)
            )
        return dashboard_gauge_configs

    @staticmethod
    def _get_gauge_config(dashboard_gauge):
        config = dashboard_gauge.to_widget()
        gauge_metric_value = get_gauge_metric_value(dashboard_gauge)
        if gauge_metric_value:
            config['value'] = gauge_metric_value
            # set max value of dial to nearest equivalent of 100
            config['max_value'] = 10 ** len(str(config['value']))
            number_of_ticks = 5
            config['major_ticks'] = [int(config['max_value'] * i / 5)
                                     for i in range(0, number_of_ticks + 1)]
        config['metric_name'] = dict(GAUGE_METRICS).get(dashboard_gauge.metric, '')
        return config


@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.CAMPAIGN_DASHBOARD.required_decorator(), name='dispatch')
# Allows ConfigurableReportView.get_ajax() to work with Bootstrap 5:
@method_decorator(use_bootstrap5, name='dispatch')
class DashboardReportView(ConfigurableReportView):
    # Set ConfigurableReportView.url to direct dashboard reports to this view:
    slug = 'dashboard_report'
    # Suppress "Export to Excel" button on filter panel:
    is_exportable = False


@method_decorator([login_and_domain_required, require_GET], name='dispatch')
class PaginatedCasesWithGPSView(BaseDomainView, CaseListMixin):
    urlname = 'api_cases_with_gps'
    search_class = CaseSearchES

    def dispatch(self, request, *args, **kwargs):
        self._request_params = json_request(request.GET)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, domain, *args, **kwargs):
        return JsonResponse(self._get_paginated_cases_with_gps())

    def _get_paginated_cases_with_gps(self):
        case_type = self.request.GET.get('case_type')
        gps_property = self.request.GET.get('gps_prop_name')

        query = self._build_query()
        query = query.case_type(case_type)
        query = query.NOT(case_property_missing(gps_property))
        query = query.sort('server_modified_on', desc=True)

        cases, total = self._get_cases_page(query)
        case_data = []
        for case_obj in cases:
            case_row = self._parse_case(case_obj, gps_property)
            if case_row:
                case_data.append(case_row)

        return {
            'items': case_data,
            'total': total,
        }

    def _base_query(self):
        return (
            self.search_class()
            .domain(self.domain)
        )

    def _parse_case(self, case_obj, gps_property):
        lat, lon = get_lat_lon_from_dict(case_obj.case_json, gps_property)

        # This is a precautionary measure for when there is a case with no GPS data
        # but the ES index hasn't been updated to reflect this yet
        if not lat and lon:
            return None

        return {
            'id': case_obj.case_id,
            'name': case_obj.name,
            'coordinates': {
                'lat': lat,
                'lng': lon,
            },
            'lat': lat,
            'lng': lon,
        }

    def _get_cases_page(self, query):
        case_ids = query.get_ids()
        page = int(self.request.GET.get('page', 1))
        limit = int(self.request.GET.get('limit', 100))

        paginator = Paginator(case_ids, limit)
        case_ids_page = list(paginator.get_page(page))

        return (
            CommCareCase.objects.get_cases(case_ids_page, self.domain, ordered=True),
            paginator.count,
        )


@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.CAMPAIGN_DASHBOARD.required_decorator(), name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class DashboardWidgetView(HqHtmxActionMixin, BaseDomainView):
    urlname = "dashboard_widget"
    form_template_partial_name = 'campaign/partials/widget_form.html'

    @property
    def section_url(self):
        return reverse(self.urlname, args=[self.domain])

    @hq_hx_action('get')
    def new_widget(self, request, *args, **kwargs):
        self._validate_request_widget_type()

        context = {
            'widget_form': self.form_class(domain=self.domain),
            'widget_type': self.widget_type,
        }
        return self.render_htmx_partial_response(request, self.form_template_partial_name, context)

    def _validate_request_widget_type(self):
        if not any(choice[0] == self.widget_type for choice in WidgetType.choices):
            raise HtmxResponseException(gettext_lazy("Requested widget type is not supported"))

    @cached_property
    def widget_type(self):
        if self.request.method == "GET":
            return self.request.GET.get('widget_type')
        else:
            return self.request.POST.get('widget_type')

    @cached_property
    def form_class(self):
        return WidgetType.get_form_class(self.widget_type)

    @property
    def dashboard(self):
        dashboard, _ = Dashboard.objects.get_or_create(domain=self.domain)
        return dashboard

    @hq_hx_action('post')
    def save_widget(self, request, *args, **kwargs):
        self._validate_request_widget_type()

        if self.widget_id:
            widget = get_object_or_404(self.model_class, pk=self.widget_id)
        else:
            widget = self.model_class(dashboard=self.dashboard)

        form = self.form_class(self.domain, request.POST, instance=widget)
        if form.is_valid():
            form.save(commit=True)
            return JsonResponse({'success': True})

        context = {
            'widget_form': form,
            'widget_type': self.widget_type,
            'widget': widget,
        }
        return self.render_htmx_partial_response(request, self.form_template_partial_name, context)

    @property
    def model_class(self):
        return WidgetType.get_model_class(self.widget_type)

    @hq_hx_action('get')
    def edit_widget(self, request, *args, **kwargs):
        self._validate_request_widget_type()

        widget = get_object_or_404(self.model_class, pk=self.widget_id)
        context = {
            'widget_form': self.form_class(self.domain, instance=widget),
            'widget_type': self.widget_type,
            'widget': widget,
        }
        return self.render_htmx_partial_response(request, self.form_template_partial_name, context)

    @cached_property
    def widget_id(self):
        if self.request.method == "GET":
            return self.request.GET.get('widget_id')
        else:
            return self.request.POST.get('widget_id')

    @hq_hx_action('post')
    def delete_widget(self, request, *args, **kwargs):
        self._validate_request_widget_type()

        widget = get_object_or_404(self.model_class, pk=self.widget_id)
        widget.delete()
        return self.render_htmx_no_response(request)


@require_GET
@login_and_domain_required
@use_bootstrap5
def get_geo_case_properties_view(request, domain):
    case_type = request.GET.get('case_type')
    if not case_type:
        return HttpResponseBadRequest(gettext_lazy('case_type param is required'))

    geo_case_props = get_geo_case_properties(domain, case_type)
    return render(
        request,
        'campaign/partials/case_properties_dropdown.html',
        {'geo_case_props': sorted(geo_case_props)},
    )


def get_geo_case_properties(domain, case_type):
    geo_case_props = get_gps_properties(domain, case_type)
    geo_case_props.add(GPS_POINT_CASE_PROPERTY)
    return geo_case_props
