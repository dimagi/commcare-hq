from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy

from corehq import toggles
from corehq.apps.case_search.const import (
    SPECIAL_CASE_PROPERTIES_MAP,
    CASE_COMPUTED_METADATA,
)
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.reports.standard.cases.utils import (
    query_location_restricted_cases,
)
from corehq.apps.reports.v2.endpoints.case_owner import CaseOwnerEndpoint
from corehq.apps.reports.v2.endpoints.case_properties import (
    CasePropertiesEndpoint,
)
from corehq.apps.reports.v2.endpoints.case_type import CaseTypeEndpoint
from corehq.apps.reports.v2.endpoints.datagrid import DatagridEndpoint
from corehq.apps.reports.v2.filters.case_report import (
    CaseOwnerReportFilter,
    CaseTypeReportFilter,
)
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
from corehq.feature_previews import (
    EXPLORE_CASE_DATA_PREVIEW,
    is_eligible_for_ecd_preview,
)


class ExploreCaseDataReport(BaseReport):
    slug = 'explore_case_data'

    data_endpoints = (
        DatagridEndpoint,
    )

    options_endpoints = (
        CasePropertiesEndpoint,
        CaseOwnerEndpoint,
        CaseTypeEndpoint,
    )

    columns = [
        ColumnMeta(
            title=ugettext_lazy("Case Name"),
            name='case_name',
            width=200,
            sort='asc',
        ),
    ]

    column_filters = [
        TextXpathColumnFilter,
        NumericXpathColumnFilter,
        DateXpathColumnFilter,
    ]

    unsortable_column_names = CASE_COMPUTED_METADATA

    report_filters = [
        CaseOwnerReportFilter,
        CaseTypeReportFilter,
    ]

    @property
    def can_view_ecd_preview(self):
        return (EXPLORE_CASE_DATA_PREVIEW.enabled_for_request(self.request) and
                is_eligible_for_ecd_preview(self.request))

    @property
    def has_permission(self):
        return ((toggles.EXPLORE_CASE_DATA.enabled_for_request(self.request)
                 or self.can_view_ecd_preview)
                and self.request.couch_user.can_edit_data())

    @property
    def initial_report_filters(self):
        return [
            ReportFilterData(
                name=CaseOwnerReportFilter.name,
                value=[
                    {
                        'text': "[{}]".format(ugettext_lazy("Project Data")),
                        'id': 'project_data',
                    },
                ],
            ),
            ReportFilterData(
                name=CaseTypeReportFilter.name,
                value=CaseTypeReportFilter.initial_value(
                    self.request, self.domain
                ),
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
            if column_context.get('sort'):
                descending = column_context['sort'] == 'desc'
                prop_name = column_context['name']

                try:
                    special_property = SPECIAL_CASE_PROPERTIES_MAP[prop_name]
                    query = query.sort(special_property.sort_property,
                                       desc=descending)
                except KeyError:
                    query = query.sort_by_case_property(prop_name,
                                                        desc=descending)

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
