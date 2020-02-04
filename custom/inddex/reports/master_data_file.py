from memoized import memoized

from custom.inddex.ucr.data_providers.master_data_file_data import MasterDataFileData
from custom.inddex.utils import BaseGapsSummaryReport


class MasterDataFileSummaryReport(BaseGapsSummaryReport):
    title = 'Output 1 - Master Data File'
    name = title
    slug = 'output_1_master_data_file'
    export_only = False
    show_filters = True

    @property
    @memoized
    def data_providers(self):
        return [
            MasterDataFileData(config=self.report_config),
        ]
