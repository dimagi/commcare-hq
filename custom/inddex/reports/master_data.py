from django.utils.functional import cached_property

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from custom.inddex.filters import (
    CaseOwnersFilter,
    DateRangeFilter,
    GapTypeFilter,
    RecallStatusFilter,
)
from custom.inddex.food import FoodData


class MasterDataReport(DatespanMixin, CustomProjectReport, GenericTabularReport):
    title = 'Output 1 - Master Data File'
    name = title
    slug = 'master_data'
    export_only = False
    exportable = True

    @property
    def fields(self):
        return [CaseOwnersFilter, DateRangeFilter, GapTypeFilter, RecallStatusFilter]

    @property
    def headers(self):
        return DataTablesHeader(
            *(DataTablesColumn(header) for header in self._food_data.headers)
        )

    @property
    def rows(self):
        return self._food_data.rows

    @cached_property
    def _food_data(self):
        return FoodData.from_request(self.domain, self.request)
