from __future__ import absolute_import, unicode_literals

from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _
from memoized import memoized

from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES_MAP,
)
from corehq.apps.case_search.filter_dsl import CaseFilterError
from corehq.apps.es.case_search import CaseSearchES, flatten_result
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.exceptions import BadRequestError
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.select import (
    CaseTypeFilter,
    SelectOpenCloseFilter,
)
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import SafeCaseDisplay
from corehq.apps.reports.standard.cases.filters import (
    CaseListExplorerColumns,
    XpathCaseSearchFilter,
)
from six.moves import range


class CaseListExplorer(CaseListReport):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

    fields = [
        CaseListFilter,
        CaseTypeFilter,
        SelectOpenCloseFilter,
        XpathCaseSearchFilter,
        CaseListExplorerColumns,
    ]

    def get_data(self):
        for row in self.es_results['hits'].get('hits', []):
            yield flatten_result(row)

    def _build_query(self):
        query = super(CaseListExplorer, self)._build_query()
        query = self._populate_sort(query)
        xpath = XpathCaseSearchFilter.get_value(self.request, self.domain)
        if xpath:
            try:
                query = query.xpath_query(self.domain, xpath)
            except CaseFilterError as e:
                error = "<p>{}.</p>".format(escape(e))
                bad_part = "<p>{} <strong>{}</strong></p>".format(
                    _("The part of your search query we didn't understand is: "),
                    escape(e.filter_part)
                ) if e.filter_part else ""
                raise BadRequestError("{}{}".format(error, bad_part))
        return query

    def _populate_sort(self, query):
        num_sort_columns = int(self.request.GET.get('iSortingCols', 0))
        for col_num in range(num_sort_columns):
            descending = self.request.GET['sSortDir_{}'.format(col_num)] == 'desc'
            column_id = int(self.request.GET["iSortCol_{}".format(col_num)])
            column = self.headers.header[column_id]
            try:
                special_property = SPECIAL_CASE_PROPERTIES_MAP[column.prop_name]
                query = query.sort(special_property.sort_property, desc=descending)
            except KeyError:
                query = query.sort_by_case_property(column.prop_name, desc=descending)
        return query

    @property
    @memoized
    def columns(self):
        return [
            DataTablesColumn(
                column,
                prop_name=column,
                visible=column not in CaseListExplorerColumns.HIDDEN_COLUMNS,
                sortable=column not in CASE_COMPUTED_METADATA,
            )
            for column in CaseListExplorerColumns.get_value(self.request, self.domain)
        ]

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
