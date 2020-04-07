from django.utils.functional import cached_property

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from custom.inddex import filters
from custom.inddex.food import FoodData


class MasterDataReport(DatespanMixin, CustomProjectReport, GenericTabularReport):
    name = 'Output 1 - Master Data File'
    slug = 'master_data'

    @property
    def fields(self):
        return [
            filters.CaseOwnersFilter,
            filters.DateRangeFilter,
            filters.GapTypeFilter,
            filters.RecallStatusFilter
        ]

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
