from django.conf import settings
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET

from memoized import memoized

from dimagi.utils.web import json_request

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.es.case_search import CaseSearchES, case_property_missing
from corehq.apps.geospatial.utils import get_lat_lon_from_dict
from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.reports.generic import get_filter_classes
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.views import BaseProjectReportSectionView
from corehq.form_processor.models import CommCareCase
from corehq.util.timezones.utils import get_timezone

from .models import Dashboard


class DashboardMapReportFilterMixin:
    """
    Provides view context for dashboard maps and reports
    """
    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
    ]

    def dashboard_map_report_filters_context(self):
        return {
            'report': {
                'title': self.page_title,
                'section_name': self.section_name,
                'show_filters': True,
                'is_async': False,  # Don't hide div #reportFiltersAccordion
            },
            'report_filters': [
                dict(field=filter_class.render(), slug=filter_class.slug)
                for filter_class in self.dashboard_map_report_filter_classes
            ],
            'report_filter_form_action_css_class': CSS_ACTION_CLASS,
        }

    @property
    @memoized
    def dashboard_map_report_filter_classes(self):
        timezone = get_timezone(self.request, self.domain)
        return get_filter_classes(self.fields, self.request, self.domain, timezone)


@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.CAMPAIGN_DASHBOARD.required_decorator(), name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class DashboardView(BaseProjectReportSectionView, DashboardMapReportFilterMixin):
    urlname = 'campaign_dashboard'
    page_title = gettext_lazy("Campaign Dashboard")
    template_name = 'campaign/dashboard.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard, __ = Dashboard.objects.get_or_create(domain=self.domain)
        map_widgets = self._dashboard_map_configs(dashboard)
        report_widgets = self._dashboard_report_configs(dashboard)
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
            'map_report_widgets': {
                'cases': sorted(
                    map_widgets['cases'] + report_widgets['cases'],
                    key=lambda x: x['display_order'],
                ),
                'mobile_workers': sorted(
                    map_widgets['mobile_workers'] + report_widgets['mobile_workers'],
                    key=lambda x: x['display_order'],
                ),
            },
        })
        context.update(self.dashboard_map_report_filters_context())
        return context

    def _dashboard_map_configs(self, dashboard):
        dashboard_map_configs = {
            'cases': [],
            'mobile_workers': [],
        }
        for dashboard_map in dashboard.maps.all():
            config = model_to_widget(dashboard_map)
            dashboard_map_configs[dashboard_map.dashboard_tab].append(config)
        return dashboard_map_configs

    def _dashboard_report_configs(self, dashboard):
        configs = {
            'cases': [],
            'mobile_workers': [],
        }
        for report in dashboard.reports.all():
            config = report_to_widget(report)
            configs[report.dashboard_tab].append(config)
        return configs


def model_to_widget(instance):
    """
    Like model_to_dict, but excludes relations, and adds 'widget_type'.
    """
    widget = instance.__dict__.copy()
    widget.pop('_state', None)  # Remove Django's internal state field
    widget['widget_type'] = instance.__class__.__name__
    return widget


def report_to_widget(instance):
    """
    Adds 'url_root' to the widget.
    """
    widget = model_to_widget(instance)
    widget['url_root'] = instance.url_root
    return widget


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
