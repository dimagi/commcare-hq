from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

from corehq.apps.domain.decorators import two_factor_exempt
from corehq.apps.hqwebapp import views as hqwebapp_views
from corehq.apps.locations.permissions import location_safe
from corehq.toggles import ICDS_MOBILE_DASHBOARD_MAPS, NAMESPACE_USER
from custom.icds_reports.dashboard_utils import get_dashboard_template_context
from custom.icds_reports.views import DASHBOARD_CHECKS


@xframe_options_exempt
def login(request, domain):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('cas_mobile_dashboard', args=[domain]))
    return hqwebapp_views.domain_login(
        request, domain,
        custom_template_name='icds_reports/mobile_login.html',
        extra_context={
            'domain': domain,
            'next': reverse('cas_mobile_dashboard', args=[domain])
        }
    )


@xframe_options_exempt
@two_factor_exempt
def logout(req, domain):
    # override logout so you are redirected to the right login page afterwards
    return hqwebapp_views.logout(req, default_domain_redirect='cas_mobile_dashboard_login')


@location_safe
@method_decorator(DASHBOARD_CHECKS, name='dispatch')
@method_decorator(xframe_options_exempt, name='dispatch')
class MobileDashboardView(TemplateView):
    template_name = 'icds_reports/mobile/dashboard/mobile_dashboard.html'

    @property
    def domain(self):
        return self.kwargs['domain']

    def get_context_data(self, **kwargs):
        kwargs.update(self.kwargs)
        kwargs.update(get_dashboard_template_context(self.domain, self.request.couch_user))
        kwargs['is_mobile'] = True
        kwargs['mobile_maps_enabled'] = ICDS_MOBILE_DASHBOARD_MAPS.enabled(self.request.user.username,
                                                                           NAMESPACE_USER)
        return super().get_context_data(**kwargs)
