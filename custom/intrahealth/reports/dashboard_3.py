# coding=utf-8
from custom.intrahealth.filters import YeksiNaaLocationFilter, MonthsDateFilter, ProgramFilter
from custom.intrahealth.sqldata import SatisfactionRateAfterDeliveryData, ValuationOfPNAStockPerProductData
from custom.intrahealth.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard3Report(MultiReport):
    title = "Tableau de Bord 3"
    fields = [MonthsDateFilter, ProgramFilter, YeksiNaaLocationFilter]
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
