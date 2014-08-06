from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from custom.care_pathways.fields import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter, \
    ScheduleCasteFilter, ScheduleTribeFilter, GroupByFilter, PPTYearFilter, TypeFilter


class AdoptionDisaggregatedReport(DatespanMixin, GetParamsMixin, GenericTabularReport, CustomProjectReport):
    name = 'Adoption Disaggregated'
    slug = 'adoption_disaggregated'
    report_title = 'Adoption Disaggregated'

    @property
    def fields(self):
        filters = [GeographyFilter,
              GroupByFilter,
              PPTYearFilter,
              TypeFilter,
              GenderFilter,
              GroupLeadershipFilter,
              CBTNameFilter,
              ]
        if self.domain == 'pathways-india-mis':
            filters.extend([ScheduleCasteFilter, ScheduleTribeFilter])

        return filters

    def headers(self):
        return []

    def rows(self):
        return []