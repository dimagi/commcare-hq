from corehq.apps.locations.models import Location
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import LocationFilter, FicheLocationFilter
from custom.intrahealth.reports import IntraHealtMixin
from custom.intrahealth.sqldata import FicheData

class FicheConsommationReport(IntraHealtMixin, DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = "Fiche Consommation"
    slug = 'fiche_consommation'
    report_title = "Fiche Consommation"
    fields = [DatespanFilter, FicheLocationFilter]
    exportable = True
    col_names = ['actual_consumption', 'billed_consumption', 'consommation-non-facturable']

    @property
    def model(self):
        return FicheData(config=self.report_config)