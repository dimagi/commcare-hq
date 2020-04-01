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
from custom.inddex.ucr_data import FoodCaseData


class MasterDataFileSummaryReport(DatespanMixin, CustomProjectReport, GenericTabularReport):
    title = 'Output 1 - Master Data File'
    name = title
    slug = 'output_1_master_data_file'
    export_only = False
    report_comment = 'This output includes all data that appears in the output files as well as background ' \
                     'data that are used to perform calculations that appear in the outputs.'

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
        return FoodData(
            self.domain,
            FoodCaseData({
                'domain': self.domain,
                'startdate': str(self.datespan.startdate),
                'enddate': str(self.datespan.enddate),
                'case_owners': self.request.GET.get('case_owners') or '',
                'gap_type': self.request.GET.get('gap_type') or '',
                'recall_status': self.request.GET.get('recall_status') or '',
            }).get_data(),
        )
