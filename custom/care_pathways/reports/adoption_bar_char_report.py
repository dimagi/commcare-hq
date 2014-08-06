import json
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from custom.care_pathways.fields import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter, \
    ScheduleCasteFilter, ScheduleTribeFilter, GroupByFilter, PPTYearFilter, TypeFilter
from custom.care_pathways.sqldata import AdoptionBarChartReportSqlData
from custom.care_pathways.utils import get_domain_configuration


class AdoptionBarChartReport(DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = 'Adoption Bar Chart'
    slug = 'adoption_bar_chart'
    report_title = 'Adoption Bar Chart'

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

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            year=self.request.GET.get('year', ''),
            value_chain=self.request.GET.get('type_value_chain', ''),
            domains=tuple(self.request.GET.getlist('type_domain', [])),
            practices=tuple(self.request.GET.getlist('type_practice', []))
        )
        return config

    @property
    def model(self):
        return AdoptionBarChartReportSqlData(domain=self.domain, config=self.report_config)

    @property
    def rows(self):
        data = self.model.data
        print data
        return []