from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from memoized import memoized

from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES_MAP,
    DOCS_LINK_CASE_LIST_EXPLORER,
)
from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.es.case_search import CaseSearchES, wrap_case_search_hit
from corehq.apps.locations.permissions import location_safe
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
    XPathCaseSearchFilter,
)
from corehq.util.metrics import metrics_histogram_timer


class XpathCaseSearchFilterMixin(object):
    """
    To be mixed in views using XPathCaseSearchFilter to apply the filter
    """
    def apply_xpath_case_search_filter(self, query):
        xpath = XPathCaseSearchFilter.get_value(self.request, self.domain)
        if xpath:
            try:
                query = query.xpath_query(self.domain, xpath)
            except CaseFilterError as e:
                track_workflow(self.request.couch_user.username, f"{self.name}: Query Error")

                error = "<p>{}.</p>".format(escape(e))
                bad_part = "<p>{} <strong>{}</strong></p>".format(
                    _("The part of your search query that caused this error is: "),
                    escape(e.filter_part)
                ) if e.filter_part else ""
                raise BadRequestError("{}{}".format(error, bad_part))

            if '/' in xpath:
                track_workflow(self.request.couch_user.username, f"{self.name}: Related case search")
        return query


@location_safe
class CaseListExplorer(CaseListReport, XpathCaseSearchFilterMixin):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES
    description = _("Use Case List Explorer to run deep searches on your cases by case properties.  ")
    documentation_link = DOCS_LINK_CASE_LIST_EXPLORER

    exportable = True
    exportable_all = True
    emailable = True
    _is_exporting = False

    fields = [
        XPathCaseSearchFilter,
        CaseListExplorerColumns,
        CaseListFilter,
        CaseTypeFilter,
        SelectOpenCloseFilter,
    ]

    @classmethod
    def get_subpages(cls):
        # Override parent implementation
        return []

    @property
    @memoized
    def es_results(self):
        timer = metrics_histogram_timer(
            'commcare.case_list_explorer_query.es_timings',
            timing_buckets=(0.01, 0.05, 1, 5),
        )
        with timer:
            return super(CaseListExplorer, self).es_results

    def _build_query(self, sort=True):
        query = super(CaseListExplorer, self)._build_query()
        query = self._populate_sort(query, sort)
        query = self.apply_xpath_case_search_filter(query)
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
                if special_property.key == '@case_id':
                    # This condition is added because ES 5 does not allow sorting on _id.
                    #  When we will have case_id in root of the document, this should be removed.
                    sort_order = 'desc' if descending else 'asc'
                    query.es_query['sort'] = [{
                        'case_properties.value.exact': {
                            'order': sort_order,
                            'nested_path': 'case_properties',
                            'nested_filter': {'term': {"case_properties.key.exact": "@case_id"}},
                        }
                    }]
                    return query
                query = query.sort(special_property.sort_property, desc=descending)
            except KeyError:
                query = query.sort_by_case_property(column.prop_name, desc=descending)
        return query

    @property
    def columns(self):
        view_case_column = DataTablesColumn(
            _("View Case"),
            prop_name='_link',
            sortable=False,
        )

        if self._is_exporting:
            persistent_cols = [
                DataTablesColumn(
                    "@case_id",
                    prop_name='@case_id',
                    sortable=True,
                )
            ]
        elif self.is_rendered_as_email:
            persistent_cols = [view_case_column]
        else:
            persistent_cols = [
                DataTablesColumn(
                    "case_name",
                    prop_name='case_name',
                    sortable=True,
                    visible=False,
                ),
                view_case_column,
            ]

        return persistent_cols + [
            DataTablesColumn(
                column["label"],
                prop_name=column["name"],
                sortable=column not in CASE_COMPUTED_METADATA,
            )
            for column in CaseListExplorerColumns.get_value(self.request, self.domain)
        ]

    @property
    def headers(self):
        column_names = [c.prop_name for c in self.columns]
        headers = DataTablesHeader(*self.columns)
        # by default, sort by name, otherwise we fall back to the case_name hidden column
        if "case_name" in column_names[1:]:
            headers.custom_sort = [[column_names[1:].index("case_name") + 1, 'asc']]
        elif "name" in column_names:
            headers.custom_sort = [[column_names.index("name"), 'asc']]
        else:
            headers.custom_sort = [[0, 'asc']]
        return headers

    @property
    def rows(self):
        self.track_search()
        data = (wrap_case_search_hit(row) for row in self.es_results['hits'].get('hits', []))
        return self._get_rows(data)

    def track_search(self):
        track_workflow(
            self.request.couch_user.username,
            f"{self.name}: Search Performed",
            self.get_tracked_search_properties()
        )

    def get_tracked_search_properties(self):
        return {
            'domain': self.domain,
        }

    @property
    def get_all_rows(self):
        query = self._build_query(sort=False)
        data = (wrap_case_search_hit(r) for r in query.scroll_ids_to_disk_and_iter_docs())
        return self._get_rows(data)

    def _get_rows(self, data):
        timer = metrics_histogram_timer(
            'commcare.case_list_explorer_query.row_fetch_timings',
            timing_buckets=(0.01, 0.05, 1, 5),
        )
        with timer:
            for case in data:
                case_display = SafeCaseDisplay(case, self.timezone, self.individual)
                yield [
                    case_display.get(column.prop_name)
                    for column in self.columns
                ]

    @property
    def export_table(self):
        self._is_exporting = True
        track_workflow(self.request.couch_user.username, f"{self.name}: Export button clicked")
        return super(CaseListExplorer, self).export_table
