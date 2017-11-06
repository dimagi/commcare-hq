from __future__ import absolute_import

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.standard import CustomProjectReport
from corehq.util import reverse


@location_safe
class DashboardReport(CustomProjectReport):
    slug = 'champ_dashboard_report'
    name = 'Prevision vs Achievements'
    title = 'Prevision vs Achievements'
    report_template_path = 'champ/dashboard.html'
