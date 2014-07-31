from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from custom.care_pathways.fields import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter, \
    ScheduleCasteFilter, ScheduleTribeFilter
from custom.care_pathways.fields import GeographyFilter, PPTYearFilter, TypeFilter


class AdoptionBarChartReport(DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = 'Adoption Bar Chart'
    slug = 'adoption_bar_chart'
    report_title = 'Adoption Bar Chart'
    fields = [GeographyFilter,
              PPTYearFilter,
              TypeFilter,
              GenderFilter,
              GroupLeadershipFilter,
              CBTNameFilter,
              ScheduleCasteFilter,
              ScheduleTribeFilter]
