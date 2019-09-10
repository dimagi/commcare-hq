from custom.intrahealth.filters import YeksiNaaLocationFilter, MonthsDateFilter, ProgramFilter
from custom.intrahealth.sqldata import AvailabilityData, RuptureRateByPPSData
from custom.intrahealth.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard1Report(MultiReport):
    title = "Tableau de Bord 1"
    fields = [MonthsDateFilter, ProgramFilter, YeksiNaaLocationFilter]
    name = "Tableau de Bord 1"
    slug = 'tableau_de_bord_1'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        return [
            AvailabilityData(config=self.report_config),
            RuptureRateByPPSData(config=self.report_config),
        ]
