from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy

from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.reports.standard.cases.utils import query_location_restricted_cases
from corehq.apps.reports.v2.endpoints.case_owner import CaseOwnerEndpoint
from corehq.apps.reports.v2.endpoints.case_properties import (
    CasePropertiesEndpoint
)
from corehq.apps.reports.v2.endpoints.datagrid import DatagridEndpoint
from corehq.apps.reports.v2.filters.case_report import CaseOwnerReportFilter
from corehq.apps.reports.v2.filters.xpath_column import (
    TextXpathColumnFilter,
    NumericXpathColumnFilter,
    DateXpathColumnFilter,
    ColumnXpathExpressionBuilder,
)
from corehq.apps.reports.v2.formatters.cases import CaseDataFormatter
from corehq.apps.reports.v2.models import (
    BaseReport,
    ColumnMeta,
    ReportFilterData,
)
from corehq.apps.es import CaseSearchES, cases as case_es


class ExploreCaseDataReport(BaseReport):
    slug = 'explore_case_data'

    data_endpoints = (
        DatagridEndpoint,
    )

    options_endpoints = (
        CasePropertiesEndpoint,
        CaseOwnerEndpoint,
    )

    columns = [
        ColumnMeta(
            title=ugettext_lazy("Case Name"),
            name='case_name',
            width=200,
        ),
        ColumnMeta(
            title=ugettext_lazy("Case Type"),
            name='@case_type',
            width=200,
        ),
    ]

    column_filters = [
        TextXpathColumnFilter,
        NumericXpathColumnFilter,
        DateXpathColumnFilter,
    ]

    report_filters = [
        CaseOwnerReportFilter,
    ]

    initial_report_filters = [
        ReportFilterData(
            name=CaseOwnerReportFilter.name,
            value=[
                {
                    'text': "[{}]".format(ugettext_lazy("Project Data")),
                    'id': 'project_data',
                },
            ],
        ),
    ]

    def _get_base_query(self):
        return (CaseSearchES()
                .domain(self.domain)
                .NOT(case_es.case_type(USER_LOCATION_OWNER_MAP_TYPE)))

    def get_data_response(self, endpoint):
        query = self._get_base_query()

        for report_filter_context in endpoint.report_context.get('reportFilters'):
            report_filter = self.get_report_filter(report_filter_context)
            query = report_filter.get_filtered_query(query)

        expressions = []
        for column_context in endpoint.report_context.get('columns', []):
            expression_builder = ColumnXpathExpressionBuilder(
                self.request,
                self.domain,
                column_context,
                self.column_filters
            )
            expression = expression_builder.get_expression()
            if expression:
                expressions.append(expression)
        if expressions:
            xpath_final = " and ".join(expressions)
            query = query.xpath_query(self.domain, xpath_final)

        # apply location restriction
        if not self.request.can_access_all_locations:
            query = query_location_restricted_cases(query, self.request)

        return endpoint.get_response(query, CaseDataFormatter)
