from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.locations.permissions import location_safe


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
