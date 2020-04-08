from django.utils.functional import cached_property

from custom.inddex import filters
from custom.inddex.food import FoodData

from .utils import MultiTabularReport


class MasterDataReport(MultiTabularReport):
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
    def data_providers(self):
        return [MasterData(self._food_data)]

    @cached_property
    def _food_data(self):
        return FoodData.from_request(self.domain, self.request)


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
