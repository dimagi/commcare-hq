from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from corehq.apps.hqwebapp import views as hqwebapp_views
from corehq.apps.locations.permissions import location_safe
from custom.icds_reports.dashboard_utils import get_dashboard_template_context
from custom.icds_reports.views import DASHBOARD_CHECKS


def login(req, domain):
    return hqwebapp_views.domain_login(req, domain, custom_template_name='icds_reports/mobile_login.html')


@location_safe
@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class MobileDashboardView(TemplateView):
    template_name = 'icds_reports/mobile/dashboard/mobile_dashboard.html'

    @property
    def domain(self):
        return self.kwargs['domain']

    def get_context_data(self, **kwargs):
        kwargs.update(self.kwargs)
        kwargs.update(get_dashboard_template_context(self.domain, self.request.couch_user))
        kwargs['is_mobile'] = True
        return super().get_context_data(**kwargs)
