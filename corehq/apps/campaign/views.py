from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.reports.views import BaseProjectReportSectionView


@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class DashboardView(BaseProjectReportSectionView):
    urlname = 'campaign_dashboard'
    page_title = gettext_lazy("Campaign Dashboard")
    template_name = 'campaign/dashboard.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])
