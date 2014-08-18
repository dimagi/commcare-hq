from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from custom.care_pathways.fields import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter, GroupByFilter, PPTYearFilter, TypeFilter, ScheduleFilter
from custom.care_pathways.utils import get_domain_configuration


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
            filters.append(ScheduleFilter)

        return filters

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            ppt_year=self.request.GET.get('year', ''),
            value_chain=self.request.GET.get('type_value_chain', ''),
            domains=tuple(self.request.GET.getlist('type_domain', [])),
            practices=tuple(self.request.GET.getlist('type_practice', [])),
            group=self.request.GET.get('group_by', ''),
            owner_id=self.request.GET.get('cbt_name', ''),
            gender=self.request.GET.get('gender', ''),
            group_leadership=self.request.GET.get('group_leadership', ''),
            schedule=self.request.GET.get('farmer_social_category', ''),
        )
        hierarchy_config = get_domain_configuration(self.domain)['geography_hierarchy']
        for k, v in sorted(hierarchy_config.iteritems(), reverse=True):
            req_prop = 'geography_%s' % v['prop']
            if self.request.GET.getlist(req_prop, []):
                config.update({k: tuple(self.request.GET.getlist(req_prop, []))})
                break
        return config

    @property
    def data_provider(self):
        return AdoptionDisaggregatedSqlData(domain=self.domain, config=self.report_config, request_params=self.request_params)


    @property
    def headers(self):
        columns = [c.data_tables_column for c in self.data_provider.columns]
        headers = DataTablesHeader(*columns)
        return headers

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.data_provider.columns, no_value=self.data_provider.no_value))
        return formatter.format(self.data_provider.data, keys=self.data_provider.keys, group_by=self.data_provider.group_by)