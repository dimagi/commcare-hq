# coding=utf-8
from corehq.apps.commtrack.models import Product
from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumnGroup, DataTablesColumn
from corehq.apps.reports.sqlreport import DataFormatter, DictDataFormat


class IntraHealthLocationMixin(object):
    @property
    def location(self):
        loc = Location.get(self.request.GET.get('location_id'))
        return loc


class IntraHealthReportConfigMixin(object):

    def config_update(self, config):
        if self.request.GET.get('location_id', ''):
            if self.location.location_type.lower() == 'district':
                config.update(dict(district_id=self.location._id))
            else:
                config.update(dict(region_id=self.location._id))

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            visit="''",
            strsd=self.datespan.startdate.strftime("%Y-%m-%d"),
            stred=self.datespan.enddate.strftime("%Y-%m-%d")
        )
        self.config_update(config)
        return config


class IntraHealtMixin(IntraHealthLocationMixin, IntraHealthReportConfigMixin):
    model = None
    groups = []
    no_value = {'sort_key': 0, 'html': 0}

    PRODUCT_NAMES = {
        'Preservatif Feminin': u'Préservatif Féminin',
        'Preservatif Masculin': u'Préservatif Masculin',
        'Depo-Provera': u'Dépo-Provera',
    }

    def _safe_get(self, dictionary, element):
        return dictionary[element] if element in dictionary else None

    @property
    def headers(self):
        header = DataTablesHeader()
        columns = self.model.columns
        if self.model.have_groups:
            header.add_column(DataTablesColumnGroup('', columns[0].data_tables_column))
        else:
            header.add_column(columns[0].data_tables_column)

        if self.model.data.keys():
            groups = list(set(zip(*self.model.data.keys())[0]))
            self.groups = sorted({self._safe_get(self.PRODUCT_NAMES, group) or group for group in groups})
        else:
            self.groups = [group.name for group in Product.by_domain(self.domain)]
        for group in self.groups:
            if self.model.have_groups:
                header.add_column(DataTablesColumnGroup(group,
                    *[columns[j].data_tables_column for j in xrange(1, len(columns))]))
            else:
                header.add_column(DataTablesColumn(group))

        return header

    @property
    def rows(self):
        data = self.model.data
        ppss = sorted(list(set(zip(*data.keys())[1]))) if data.keys() else []

        rows = []

        formatter = DataFormatter(DictDataFormat(self.model.columns, no_value=self.no_value))
        data = dict(formatter.format(self.model.data, keys=self.model.keys, group_by=self.model.group_by))
        reversed_map = dict(zip(self.PRODUCT_NAMES.values(), self.PRODUCT_NAMES.keys()))
        for pps in ppss:
            row = [pps]
            for group in self.groups:
                if (group, pps) in data:
                    product = data[(group, pps)]
                    row.extend([product[p] for p in self.model.col_names])
                elif (self._safe_get(reversed_map, group), pps) in data:
                    product = data[(reversed_map[group], pps)]
                    row.extend([product[p] for p in self.model.col_names])
                else:
                    row.extend([self.no_value for p in self.model.col_names])
            rows.append(row)
        return rows
