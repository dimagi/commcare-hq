from custom.inddex import filters
from custom.inddex.food import FoodData

from .utils import MultiTabularReport


class MasterDataReport(MultiTabularReport):
    name = 'Output 1 - Master Data File'
    slug = 'master_data'
    export_only = True

    @property
    def fields(self):
        return [
            filters.CaseOwnersFilter,
            filters.DateRangeFilter,
            filters.GapTypeFilter,
            filters.RecallStatusFilter
        ]

    @property
    def data_providers(self):
        food_data = FoodData.from_request(self.domain, self.request)
        return [MasterData(food_data)]


class MasterData:
    title = "master_data"
    slug = title

    def __init__(self, food_data):
        self._food_data = food_data

    @property
    def headers(self):
        return self._food_data.headers

    @property
    def rows(self):
        return self._food_data.rows
