from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import reverse

from corehq import toggles
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.standard import CustomProjectReport


@location_safe
class DashboardReport(CustomProjectReport):
    slug = 'dashboard_report'
    name = 'AAA Convergence Dashboard'

    @classmethod
    def get_url(cls, domain=None, **kwargs):
        return reverse('program_overview', args=[domain])

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return toggles.DASHBOARD_REACH_REPORT.enabled(domain)
