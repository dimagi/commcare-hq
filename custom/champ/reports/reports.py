from __future__ import absolute_import

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.standard import CustomProjectReport


@location_safe
class PrevisionVsAchievementsGraphReport(CustomProjectReport):
    slug = 'prevision_vs_achievements_graph_report'
    name = 'Prevision vs Achievements Graph'
    title = 'Prevision vs Achievements Graph'
    base_template = 'champ/base_template.html'
    report_template_path = 'champ/prevision_vs_achievements_graph.html'


@location_safe
class PrevisionVsAchievementsTableReport(CustomProjectReport):
    slug = 'prevision_vs_achievements_table_report'
    name = 'Prevision vs Achievements Table'
    title = 'Prevision vs Achievements Table'
    base_template = 'champ/base_template.html'
    report_template_path = 'champ/prevision_vs_achievements_table.html'


@location_safe
class ServicesUptakeReport(CustomProjectReport):
    slug = 'service_uptake_report'
    name = 'Services Uptake'
    title = 'Services Uptake'
    base_template = 'champ/base_template.html'
    report_template_path = 'champ/service_uptake.html'
