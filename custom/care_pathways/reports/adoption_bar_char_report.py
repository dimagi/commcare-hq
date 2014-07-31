from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from custom.care_pathways.fields import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter, \
    ScheduleCasteFilter, ScheduleTribeFilter


class AdoptionBarChartReport(DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = 'Adoption Bar Chart'
    slug = 'adoption_bar_chart'
    report_title = 'Adoption Bar Chart'
    fields = [GeographyFilter,
              GenderFilter,
              GroupLeadershipFilter,
              CBTNameFilter,
              ScheduleCasteFilter,
              ScheduleTribeFilter]
