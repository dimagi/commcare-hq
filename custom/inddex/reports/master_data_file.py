from django.utils.functional import cached_property

from memoized import memoized

from custom.inddex.food import FoodData
from custom.inddex.ucr_data import FoodCaseData
from custom.inddex.utils import BaseGapsSummaryReport


class MasterDataFileSummaryReport(BaseGapsSummaryReport):
    title = 'Output 1 - Master Data File'
    name = title
    slug = 'output_1_master_data_file'
    export_only = False
    show_filters = True
    report_comment = 'This output includes all data that appears in the output files as well as background ' \
                     'data that are used to perform calculations that appear in the outputs.'

    @property
    @memoized
    def data_providers(self):
        return [
            MasterDataFileData(config=self.report_config),
        ]


class MasterDataFileData:
    title = 'Master Data'
    slug = 'master_data'

    def __init__(self, config):
        self.config = config

    @cached_property
    def food_data(self):
        return FoodData(
            self.config['domain'],
            FoodCaseData(self.config).get_data(),
        )

    @property
    def headers(self):
        return self.food_data.headers

    @property
    def rows(self):
        return self.food_data.rows
