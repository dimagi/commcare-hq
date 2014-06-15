from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumnGroup
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import DataFormatter, TableDataFormat, DictDataFormat
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from custom.intrahealth.sqldata import FicheData

class FicheConsommationReport(DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = "Fiche Consommation"
    slug = 'fiche_consommation'
    report_title = "Fiche Consommation"
    fields = [DatespanFilter, AsyncLocationFilter]
    no_value = {'sort_key': 0, 'html': '0'}
    groups = []

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
        return config

    @property
    def headers(self):
        header = DataTablesHeader()
        columns = self.model.columns
        header.add_column(DataTablesColumnGroup('', columns[0].data_tables_column))
        self.groups = sorted(list(set(zip(*self.model.data.keys())[0])))
        for group in self.groups:
            header.add_column(DataTablesColumnGroup(group,
                                                    *[columns[j].data_tables_column for j in xrange(1, len(columns))]))
        return header

    @property
    def model(self):
        return FicheData(config=self.report_config)

    @property
    def rows(self):
        data = self.model.data
        ppss = sorted(list(set(zip(*data.keys())[1])))
        rows = []

        formatter = DataFormatter(DictDataFormat(self.model.columns, no_value=self.no_value))
        data = dict(formatter.format(self.model.data, keys=self.model.keys, group_by=self.model.group_by))
        for pps in ppss:
            row = [pps]
            for group in self.groups:
                if (group, pps) in data:
                    product = data[(group, pps)]
                    row += [product['actual_consumption'], product['billed_consumption'], product['consommation-non-facturable']]
                else:
                    row += [self.no_value, self.no_value, self.no_value]
            rows.append(row)
        return rows