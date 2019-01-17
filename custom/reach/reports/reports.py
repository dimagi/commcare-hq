from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import reverse

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.standard import CustomProjectReport


@location_safe
class DashboardReport(CustomProjectReport):
    slug = 'dashboard_report'
    name = 'REACH Dashboard'

    @classmethod
    def get_url(cls, domain=None, **kwargs):
        return reverse('reach_dashboard', args=[domain])

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        #TODO replace to new feature flag
        return True
