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
from corehq.apps.campaign.models import Dashboard
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


@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.CAMPAIGN_DASHBOARD.required_decorator(), name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class DashboardView(BaseProjectReportSectionView, DashboardMapFilterMixin):
    urlname = 'campaign_dashboard'
    page_title = gettext_lazy("Campaign Dashboard")
    template_name = 'campaign/dashboard.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
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
            'map_report_widgets': self.dashboard.get_map_report_widgets_by_tab()
        })
        context.update(self.dashboard_map_case_filters_context())
        return context


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
