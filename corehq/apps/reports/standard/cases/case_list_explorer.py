from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

from corehq.apps.case_search.filter_dsl import get_properties_from_xpath
from corehq.apps.es.case_search import CaseSearchES, flatten_result
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.standard.cases.basic import CaseListReport


class CaseListExplorer(CaseListReport):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        'corehq.apps.reports.standard.cases.filters.XpathCaseSearchFilter',
        'corehq.apps.reports.standard.cases.filters.CaseListExplorerColumns',
    ]

    def get_data(self):
        for row in self.es_results['hits'].get('hits', []):
            yield flatten_result(row)

    def _build_query(self):
        query = super(CaseListExplorer, self)._build_query()
        xpath = self.request.GET.get('search_xpath')
        if xpath:
            query = query.xpath_query(self.domain, xpath)
        return query

    @property
    def columns(self):
        default_columns = [
            DataTablesColumn("name", prop_name="name.exact"),
        ]
        filter_columns = []
        xpath = self.request.GET.get('search_xpath')
        if xpath:
            filter_columns = [DataTablesColumn(c, prop_name=c) for c in get_properties_from_xpath(xpath)]

        return default_columns + filter_columns

    @property
    def headers(self):
        return DataTablesHeader(*self.columns)

    @property
    def rows(self):
        for case in self.get_data():
            yield [
                case.get(column.prop_name.split('.')[0], '')
                for column in self.columns
            ]
