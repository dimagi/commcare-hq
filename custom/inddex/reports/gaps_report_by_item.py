from custom.inddex.ucr.data_providers.gaps_report_by_item_data import GapsReportByItemDetailsData, \
    GapsReportByItemSummaryData
from custom.inddex.ucr.report_bases.gaps_report_by_item import GapsReportByItemBase


class GapsReportByItem(GapsReportByItemBase):
    title = '1b: Gaps Report By Item'
    name = title
    slug = 'gaps_report_by_item'

    @property
    def data_providers(self):
        return [
            GapsReportByItemSummaryData(config=self.report_config),
            GapsReportByItemDetailsData(config=self.report_config)
        ]
