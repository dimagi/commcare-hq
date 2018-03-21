# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from custom.yeksi_naa_reports.filters import LocationFilter, MonthsDateFilter
from custom.yeksi_naa_reports.sqldata import ValuationOfPNAStockPerProductData
from custom.yeksi_naa_reports.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard3Report(MultiReport):
    title = "Dashboard 3"
    fields = [MonthsDateFilter, LocationFilter]
    name = "Dashboard 3"
    slug = 'dashboard_3'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        return [
            ValuationOfPNAStockPerProductData(config=self.report_config),
        ]
