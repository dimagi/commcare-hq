from custom.intrahealth.filters import YeksiNaaLocationFilter, MonthsDateFilter, ProgramFilter
from custom.intrahealth.sqldata import SatisfactionRateAfterDeliveryData, ValuationOfPNAStockPerProductData
from custom.intrahealth.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard3Report(MultiReport):
    title = "Valorisation & Satisfaction"
    fields = [MonthsDateFilter, ProgramFilter, YeksiNaaLocationFilter]
    name = "Valorisation & Satisfaction"
    slug = 'valorisation_and_satisfaction'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        return [
            SatisfactionRateAfterDeliveryData(config=self.report_config),
            ValuationOfPNAStockPerProductData(config=self.report_config),
        ]
