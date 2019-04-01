from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy

from corehq.apps.reports.v2.endpoints.case_properties import (
    CasePropertiesEndpoint
)
from corehq.apps.reports.v2.endpoints.datagrid import DatagridEndpoint
from corehq.apps.reports.v2.filters.case_columns import TextCaseColumnFilter
from corehq.apps.reports.v2.formatters.cases import CaseDataFormatter
from corehq.apps.reports.v2.models import (
    BaseReport,
    ColumnContext,
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
        ColumnContext(
            title=ugettext_lazy("Case Name"),
            name='case_name',
            width=200,
        ),
        ColumnContext(
            title=ugettext_lazy("Case Type"),
            name='@case_type',
            width=200,
        ),
    ]

    column_filters = (
        TextCaseColumnFilter,
    )

    def _get_base_query(self):
        return CaseSearchES().domain(self.domain)

    def get_data_response(self, endpoint):
        query = self._get_base_query()

        # todo think about filtering
        # for f in self.get_filters():
        #     query = f.get_filtered_query(query)

        return endpoint.get_response(query, CaseDataFormatter)
