from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import FicheLocationFilter
from custom.intrahealth.reports.utils import IntraHealtMixin
from custom.intrahealth.sqldata import FicheData


class FicheConsommationReport(IntraHealtMixin, DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = "Fiche Consommation"
    slug = 'fiche_consommation'
    report_title = "Fiche Consommation"
    fields = [DatespanFilter, FicheLocationFilter]
    exportable = True
    col_names = ['actual_consumption', 'billed_consumption', 'consommation-non-facturable']
    export_format_override = 'csv'

    @property
    def model(self):
        config = self.report_config
        locations = []
        if 'region_id' in config:
            locations = tuple(SQLLocation.objects.get(
                location_id=config['region_id']
            ).archived_descendants().values_list('location_id', flat=True))
        elif 'district_id' in config:
            locations = tuple(SQLLocation.objects.get(
                location_id=config['district_id']
            ).archived_descendants().values_list('location_id', flat=True))

        if locations:
            config.update({'archived_locations': locations})
        return FicheData(config=config)

    @property
    def export_table(self):
        table = list(super(FicheConsommationReport, self).export_table)
        #  remove first row from table headers
        replace = ''
        for k, v in enumerate(table[0][1][0]):
            if v != ' ':
                replace = v
            else:
                table[0][1][0][k] = replace

        return table
