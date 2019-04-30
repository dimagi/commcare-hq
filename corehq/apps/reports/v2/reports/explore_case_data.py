from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy

from corehq.apps.reports.v2.endpoints.case_properties import (
    CasePropertiesEndpoint
)
from corehq.apps.reports.v2.endpoints.datagrid import DatagridEndpoint
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
)
from corehq.apps.es import CaseSearchES


class ExploreCaseDataReport(BaseReport):
    slug = 'explore_case_data'

    data_endpoints = (
        DatagridEndpoint,
    )

    options_endpoints = (
        CasePropertiesEndpoint,
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

    def _get_base_query(self):
        return CaseSearchES().domain(self.domain)

    def get_data_response(self, endpoint):
        query = self._get_base_query()

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

        return endpoint.get_response(query, CaseDataFormatter)
