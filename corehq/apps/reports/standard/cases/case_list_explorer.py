from __future__ import absolute_import, unicode_literals

from io import BytesIO

import six
from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _
from jq import jq
from memoized import memoized

from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES,
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
from corehq.elastic import iter_es_docs_from_query
from couchexport.export import Format


class CaseListExplorer(CaseListReport):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

    exportable = True
    exportable_all = True
    _is_exporting = False
    export_format_override = Format.UNZIPPED_CSV

    fields = [
        CaseListFilter,
        CaseTypeFilter,
        SelectOpenCloseFilter,
        XpathCaseSearchFilter,
        CaseListExplorerColumns,
    ]

    @property
    def excel_response(self):
        self._is_exporting = True
        return BytesIO("\n".join(self.get_data()).encode('UTF-8'))

    def get_data(self):
        if self._is_exporting:
            return self._get_export_data()
        else:
            return (flatten_result(row) for row in self.es_results['hits'].get('hits', []))

    def _get_export_data(self):
        headers = ",".join(['_id'] + [c['label'] for c in self._filter_columns])

        case_docs = {r['_id']: flatten_result(r) for r in iter_es_docs_from_query(self._build_query())}
        from corehq.util.log import with_progress_bar
        computed_properties = [c for c in self._filter_columns if c['name'] in CASE_COMPUTED_METADATA]
        if computed_properties:
            for case_id, case_doc in with_progress_bar(six.iteritems(case_docs), length=len(list(case_docs.values()))):
                case_display = SafeCaseDisplay(self, case_doc)
                for computed_property in computed_properties:
                    case_doc[computed_property['name']] = case_display.get(computed_property)

        properties = ['_id']
        for c in self._filter_columns:
            try:
                prop = SPECIAL_CASE_PROPERTIES_MAP[c['name']].doc_property
            except KeyError:
                prop = c['name']
            properties.append(prop)

        jq_query_properties = ",".join('."{}"'.format(prop) for prop in properties)
        rows = jq('.[] | [{}] | @csv'.format(jq_query_properties)).transform(
            case_docs, multiple_output=True)

        return [headers] + rows

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
        if self._is_exporting:
            # Don't sort on export
            query = query.set_sorting_block({})
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
    @memoized
    def columns(self):
        return [
            DataTablesColumn(
                column['label'],
                prop_name=column['name'],
                visible=(not column.get('hidden')),
                sortable=column['name'] not in CASE_COMPUTED_METADATA,
            )
            for column in self._filter_columns
        ]

    @property
    def _filter_columns(self):
        """Columns from the report filter
        """
        if self._is_exporting:
            return [
                c for c in CaseListExplorerColumns.get_value(self.request, self.domain)
                if c['name'] not in [p['name'] for p in CaseListExplorerColumns.PERSISTENT_COLUMNS]
            ]
        return CaseListExplorerColumns.get_value(self.request, self.domain)

    @property
    def headers(self):
        header = DataTablesHeader(*self.columns)
        header.custom_sort = [[0, 'desc']]
        return header

    @property
    def rows(self):
        for case in self.get_data():
            case_display = SafeCaseDisplay(self, case)
            yield [
                case_display.get(column)
                for column in self._filter_columns
            ]

    @property
    def export_rows(self):
        self._is_exporting = True
        return self.rows
