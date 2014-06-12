from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumnGroup
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import DataFormatter, TableDataFormat
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from custom.intrahealth.sqldata import FicheData

class FicheConsommationReport(DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = "Fiche Consommation"
    slug = 'fiche_consommation'
    report_title = "Fiche Consommation"
    fields = [DatespanFilter, AsyncLocationFilter]
    GROUPS = ['DIU', 'Jadelle', u'D\xe9po', 'Microlut', 'Microgynon', 'Cond. Masc', 'Cond. Fem', 'Collier']
    no_value = {'sort_key': 0, 'html': '--'}

    @property
    def location(self):
        loc = Location.get(self.request.GET.get('location_id'))
        return loc

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            visit="''",
        )
        if self.request.GET.get('location_id', ''):
            if self.location.location_type.lower() == 'district':
                config.update(dict(district_id=self.location._id))
            else:
                config.update(dict(region_id=self.location._id))
        print config

        return config

    @property
    def headers(self):
        header = DataTablesHeader()
        i = 1
        header.add_column(DataTablesColumnGroup('', self.model.columns[0].data_tables_column))
        for group in self.GROUPS:
            header.add_column(DataTablesColumnGroup(group, *[self.model.columns[j].data_tables_column for j in xrange(i, i + 3)]))
            #header.add_column(DataTablesColumnGroup(group, *[c.data_tables_column for c in self.model.columns]))

        return header

    @property
    def model(self):
        return FicheData(config=self.report_config)

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.model.columns, no_value=self.no_value))
        return list(formatter.format(self.model.data, keys=self.model.keys, group_by=self.model.group_by))