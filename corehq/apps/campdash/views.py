from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.locations.permissions import location_safe

from .models import CampaignDashboard, DashboardGauge, DashboardReport, DashboardMap


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(login_and_domain_required, name='dispatch')
@location_safe
class CampaignDashboardView(BasePageView, DomainViewMixin):
    """
    Main view for the campaign dashboard
    """
    urlname = 'campaign_dashboard'
    page_title = gettext_lazy("Campaign Dashboard")
    template_name = 'campdash/dashboard.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        # For initial implementation, we'll use static data
        # Later this will be replaced with dynamic data from the database
        
        # Sample gauge data
        gauges = [
            {
                'title': _('Progress'),
                'value': 65,
                'min': 0,
                'max': 100,
                'type': 'progress',
            },
            {
                'title': _('Completion Rate'),
                'value': 75,
                'min': 0,
                'max': 100,
                'type': 'percentage',
            },
            {
                'title': _('Total Cases'),
                'value': 1250,
                'min': 0,
                'max': 2000,
                'type': 'count',
            },
        ]
        
        # Sample report data
        report = {
            'title': _('Campaign Progress by Region'),
            'type': 'table',
            'headers': [_('Region'), _('Target'), _('Completed'), _('Progress')],
            'rows': [
                ['North', 500, 350, '70%'],
                ['South', 600, 390, '65%'],
                ['East', 450, 320, '71%'],
                ['West', 550, 410, '75%'],
            ],
        }
        
        # Sample map data
        map_data = {
            'title': _('Geographic Distribution'),
            'type': 'markers',
            'center': [0, 0],  # Default center
            'zoom': 2,  # Default zoom level
            'markers': [],  # Will be populated dynamically
        }
        
        context = {
            'gauges': gauges,
            'report': report,
            'map_data': map_data,
            'domain': self.domain,
        }
        
        return context


@login_and_domain_required
@location_safe
def campaign_dashboard_data(request, domain):
    """
    API endpoint to get dashboard data
    """
    dashboard_id = request.GET.get('dashboard_id')
    
    # For initial implementation, return static data
    # Later this will be replaced with dynamic data from the database
    
    data = {
        'gauges': [
            {
                'title': 'Progress',
                'value': 65,
                'min': 0,
                'max': 100,
                'type': 'progress',
            },
            {
                'title': 'Completion Rate',
                'value': 75,
                'min': 0,
                'max': 100,
                'type': 'percentage',
            },
            {
                'title': 'Total Cases',
                'value': 1250,
                'min': 0,
                'max': 2000,
                'type': 'count',
            },
        ],
        'report': {
            'title': 'Campaign Progress by Region',
            'type': 'table',
            'headers': ['Region', 'Target', 'Completed', 'Progress'],
            'rows': [
                ['North', 500, 350, '70%'],
                ['South', 600, 390, '65%'],
                ['East', 450, 320, '71%'],
                ['West', 550, 410, '75%'],
            ],
        },
        'map': {
            'title': 'Geographic Distribution',
            'type': 'markers',
            'center': [0, 0],
            'zoom': 2,
            'markers': [
                {'lat': 40.7128, 'lng': -74.0060, 'label': 'New York', 'value': 350},
                {'lat': 34.0522, 'lng': -118.2437, 'label': 'Los Angeles', 'value': 290},
                {'lat': 41.8781, 'lng': -87.6298, 'label': 'Chicago', 'value': 210},
                {'lat': 29.7604, 'lng': -95.3698, 'label': 'Houston', 'value': 180},
            ],
        },
    }
    
    return JsonResponse(data)
