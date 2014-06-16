from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumnGroup, DataTablesColumn
from corehq.apps.reports.sqlreport import DataFormatter, DictDataFormat


class IntraHealtMixin(object):
    model = None
    groups = []
    no_value = {'sort_key': 0, 'html': 0}

    PRODUCT_NAMES = {
        'Preservatif Feminin': u'Pr\xe9servatif F\xe9minin',
        'Preservatif Masculin': u'Pr\xe9servatif Masculin',
        'Depo-Provera': u'D\xe9po-Provera',
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

        self.groups = list(set(zip(*self.model.data.keys())[0]))
        self.groups = sorted(set(map(lambda group: self._safe_get(self.PRODUCT_NAMES, group) or group, self.groups)))
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
        ppss = sorted(list(set(zip(*data.keys())[1])))
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
