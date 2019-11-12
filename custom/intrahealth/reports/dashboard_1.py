from custom.intrahealth.filters import YeksiNaaLocationFilter, MonthsDateFilter, ProgramFilter
from custom.intrahealth.sqldata import AvailabilityData, RuptureRateByPPSData
from custom.intrahealth.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard1Report(MultiReport):
    title = "Etat du Stock par Gamme de Produits"
    fields = [MonthsDateFilter, ProgramFilter, YeksiNaaLocationFilter]
    name = "Etat du Stock par Gamme de Produits"
    slug = 'etat_du_stock_par_gamme_de_produits'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        return [
            AvailabilityData(config=self.report_config),
            RuptureRateByPPSData(config=self.report_config),
        ]
