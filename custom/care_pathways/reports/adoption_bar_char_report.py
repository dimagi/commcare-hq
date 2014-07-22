from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport


class AdoptionBarChartReport(DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = 'Adoption Bar Chart'
    slug = 'adoption_bar_chart'
    report_title = 'Adoption Bar Chart'
    fields = []
