from __future__ import absolute_import, unicode_literals

from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _

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
from corehq.elastic import iter_es_docs_from_query


class CaseListExplorer(CaseListReport):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

    exportable = True
    exportable_all = True
    _is_exporting = False

    fields = [
        CaseListFilter,
        CaseTypeFilter,
        SelectOpenCloseFilter,
        XpathCaseSearchFilter,
        CaseListExplorerColumns,
    ]

    def _build_query(self, sort=True):
        query = super(CaseListExplorer, self)._build_query()
        query = self._populate_sort(query, sort)
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

    def _populate_sort(self, query, sort):
        if not sort:
            # Don't sort on export
            query = query.set_sorting_block(['_doc'])
            return query

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
    def headers(self):
        header = DataTablesHeader(*self.columns)
        header.custom_sort = [[0, 'desc']]
        return header

    @property
    def columns(self):
        return [
            DataTablesColumn(
                column,
                prop_name=column,
                visible=column not in CaseListExplorerColumns.HIDDEN_COLUMNS,
                sortable=column not in CASE_COMPUTED_METADATA,
            )
            for column in self._columns
        ]

    @property
    def _columns(self):
        """Columns from the report filter
        """
        if self._is_exporting:
            return CaseListExplorerColumns.EXPORT_PERSISTENT_COLUMNS + [
                c for c in CaseListExplorerColumns.get_value(self.request, self.domain)
                if c['name'] not in [p['name'] for p in CaseListExplorerColumns.PERSISTENT_COLUMNS]
            ]
        return CaseListExplorerColumns.get_value(self.request, self.domain)

    @property
    def rows(self):
        data = (flatten_result(row) for row in self.es_results['hits'].get('hits', []))
        return self._get_rows(data)

    @property
    def get_all_rows(self):
        data = (flatten_result(r) for r in iter_es_docs_from_query(self._build_query(sort=False)))
        return self._get_rows(data)

    def _get_rows(self, data):
        for case in data:
            case_display = SafeCaseDisplay(self, case)
            yield [
                case_display.get(column)
                for column in self._columns
            ]

    @property
    def export_table(self):
        self._is_exporting = True
        return super(CaseListExplorer, self).export_table
