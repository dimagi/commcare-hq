from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.permissions import location_safe
from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class DashboardView(TemplateView):
    template_name = 'reach/dashboard.html'

    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def couch_user(self):
        return self.request.couch_user

    def get_context_data(self, **kwargs):
        return super(DashboardView, self).get_context_data(**kwargs)

