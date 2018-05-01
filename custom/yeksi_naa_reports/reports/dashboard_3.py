# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from custom.yeksi_naa_reports.filters import LocationFilter, MonthsDateFilter, ProgramFilter
from custom.yeksi_naa_reports.sqldata import SatisfactionRateAfterDeliveryData, ValuationOfPNAStockPerProductData
from custom.yeksi_naa_reports.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard3Report(MultiReport):
    title = "Tableau de Bord 3"
    fields = [MonthsDateFilter, ProgramFilter, LocationFilter]
    name = "Tableau de Bord 3"
    slug = 'tableau_de_bord_3'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        return [
            SatisfactionRateAfterDeliveryData(config=self.report_config),
            ValuationOfPNAStockPerProductData(config=self.report_config),
        ]
