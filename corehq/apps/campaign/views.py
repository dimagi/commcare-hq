from django.conf import settings
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from memoized import memoized

from corehq import toggles
from corehq.apps.campaign.models import Dashboard
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.reports.generic import get_filter_classes
from corehq.apps.reports.views import BaseProjectReportSectionView
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
            'map_widgets': self._dashboard_map_configs,
        })
        context.update(self.dashboard_map_case_filters_context())
        return context

    @property
    def _dashboard_map_configs(self):
        dashboard_maps = Dashboard.objects.get(domain=self.domain).maps.all()
        dashboard_map_configs = {
            'cases': [],
            'mobile_workers': [],
        }
        for dashboard_map in dashboard_maps:
            config = {
                'id': dashboard_map.id,
                'title': dashboard_map.title,
                'case_type': dashboard_map.case_type,
                'gps_prop_name': dashboard_map.geo_case_property,
            }
            if dashboard_map.dashboard_tab == 'cases':
                dashboard_map_configs['cases'].append(config)
            else:
                dashboard_map_configs['mobile_workers'].append(config)
        return dashboard_map_configs
