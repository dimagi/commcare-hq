from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.reports.v2.endpoints.datatables import DataTablesDataEndpoint
from corehq.apps.reports.v2.formatters.cases import CaseDataFormatter
from corehq.apps.reports.v2.models import (
    BaseReport,
)
from corehq.apps.es import CaseSearchES


class ExploreCaseDataReport(BaseReport):
    slug = 'explore_case_data'

    data_endpoints = (
        DataTablesDataEndpoint,
    )

    filter_endpoints = (
    )

    def _get_base_query(self):
        return CaseSearchES().domain(self.domain)

    def get_data_response(self, endpoint):
        query = self._get_base_query()

        for f in self.get_filters():
            query = f.get_filtered_query(query)

        return endpoint.get_response(query, CaseDataFormatter)
