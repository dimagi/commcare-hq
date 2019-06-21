# coding=utf-8
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _

from memoized import memoized
from six.moves import range

from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES_MAP,
)
from corehq.apps.case_search.filter_dsl import CaseFilterError
from corehq.apps.es.case_search import CaseSearchES, flatten_result
from corehq.apps.hqwebapp.tasks import send_mail_async
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
from corehq.util.datadog.gauges import datadog_bucket_timer


class CaseListExplorer(CaseListReport):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

    exportable = True
    exportable_all = True
    emailable = True
    _is_exporting = False

    fields = [
        XpathCaseSearchFilter,
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
        timer = datadog_bucket_timer(
            'commcare.case_list_explorer_query.es_timings',
            tags=[],
            timing_buckets=(0.01, 0.05, 1, 5),
        )
        with timer:
            return super(CaseListExplorer, self).es_results

    def _build_query(self, sort=True):
        query = super(CaseListExplorer, self)._build_query()
        query = self._populate_sort(query, sort)
        xpath = XpathCaseSearchFilter.get_value(self.request, self.domain)
        if xpath:
            try:
                query = query.xpath_query(self.domain, xpath)
            except CaseFilterError as e:
                track_workflow(self.request.couch_user.username, "Case List Explorer: Query Error")

                error = "<p>{}.</p>".format(escape(e))
                bad_part = "<p>{} <strong>{}</strong></p>".format(
                    _("The part of your search query that caused this error is: "),
                    escape(e.filter_part)
                ) if e.filter_part else ""
                raise BadRequestError("{}{}".format(error, bad_part))

            if '/' in xpath:
                track_workflow(self.request.couch_user.username, "Case List Explorer: Related case search")

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
    def columns(self):
        if self._is_exporting:
            persistent_cols = [
                DataTablesColumn(
                    "@case_id",
                    prop_name='@case_id',
                    sortable=True,
                )
            ]
        else:
            persistent_cols = [
                DataTablesColumn(
                    "case_name",
                    prop_name='case_name',
                    sortable=True,
                    visible=False,
                ),
                DataTablesColumn(
                    _("View Case"),
                    prop_name='_link',
                    sortable=False,
                )
            ]

        return persistent_cols + [
            DataTablesColumn(
                column,
                prop_name=column,
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
        track_workflow(self.request.couch_user.username, "Case List Explorer: Search Performed")
        send_email_to_dev_more(
            self.domain,
            self.request.couch_user.username,
            XpathCaseSearchFilter.get_value(self.request, self.domain),
            self.es_results['hits'].get('total', 0)
        )
        data = (flatten_result(row) for row in self.es_results['hits'].get('hits', []))
        return self._get_rows(data)

    @property
    def get_all_rows(self):
        data = (flatten_result(r) for r in iter_es_docs_from_query(self._build_query(sort=False)))
        return self._get_rows(data)

    def _get_rows(self, data):
        timer = datadog_bucket_timer(
            'commcare.case_list_explorer_query.row_fetch_timings',
            tags=[],
            timing_buckets=(0.01, 0.05, 1, 5),
        )
        with timer:
            for case in data:
                case_display = SafeCaseDisplay(self, case)
                yield [
                    case_display.get(column.prop_name)
                    for column in self.columns
                ]

    @property
    def export_table(self):
        self._is_exporting = True
        track_workflow(self.request.couch_user.username, "Case List Explorer: Export button clicked")
        return super(CaseListExplorer, self).export_table


def send_email_to_dev_more(domain, user, query, total_results):
    """Dev wanted an email with every query that is performed on the CLE.

    ¯\_(ツ)_/¯
    """

    message = """
    Hi Dev! Someone just performed a query with the case list explorer. Cool!

    Domain: {}
    User: {}
    Query: {}
    Total Results: {}

    Yours truly,
    CLEBOT
    """.format(domain, user, query if query else "Empty Query", total_results)

    send_mail_async.delay(
        subject="Case List Explorer Query Performed",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=["@".join(['dmore', 'dimagi.com'])],
    )
