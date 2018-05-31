from __future__ import absolute_import, unicode_literals


from django.utils.translation import ugettext_lazy as _
from memoized import memoized

from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES_MAP
from corehq.apps.es.case_search import CaseSearchES, flatten_result
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import SafeCaseDisplay
from corehq.apps.reports.standard.cases.filters import (
    CaseListExplorerColumns,
    XpathCaseSearchFilter,
)


class CaseListExplorer(CaseListReport):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        XpathCaseSearchFilter,
        CaseListExplorerColumns,
    ]

    def get_data(self):
        for row in self.es_results['hits'].get('hits', []):
            yield flatten_result(row)

    def _build_query(self):
        query = super(CaseListExplorer, self)._build_query()
        xpath = XpathCaseSearchFilter.get_value(self.request, self.domain)
        if xpath:
            query = query.xpath_query(self.domain, xpath)
        return query

    @property
    @memoized
    def columns(self):
        user_columns = []
        for column in CaseListExplorerColumns.get_value(self.request, self.domain):
            try:
                special_property = SPECIAL_CASE_PROPERTIES_MAP[column['name']]
                user_columns.append(
                    DataTablesColumn(
                        column['label'],
                        prop_name=special_property.sort_property,
                        visible=(not column.get('hidden')),
                    ))
            except KeyError:
                user_columns.append(DataTablesColumn(
                    column['label'],
                    prop_name=column['name'],
                    visible=(not column.get('hidden')),
                ))

        return user_columns

    @property
    def headers(self):
        header = DataTablesHeader(*self.columns)
        header.custom_sort = [[0, 'desc']]
        return header

    @property
    def rows(self):
        columns = CaseListExplorerColumns.get_value(self.request, self.domain)
        for case in self.get_data():
            case_display = SafeCaseDisplay(self, case)
            yield [
                case_display.get(column)
                for column in columns
            ]
