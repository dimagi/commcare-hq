# coding=utf-8
import calendar
from corehq.apps.products.models import SQLProduct
from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumnGroup, DataTablesColumn
from corehq.apps.reports.sqlreport import DataFormatter, DictDataFormat
from corehq.util.translation import localize
from custom.intrahealth.sqldata import NombreData, TauxConsommationData
from django.utils.translation import ugettext as _
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_date


def get_localized_months():
    #Returns chronological list of months in french language
    with localize('fr'):
        return [(_(calendar.month_name[i])).title() for i in xrange(1, 13)]


class IntraHealthLocationMixin(object):

    @property
    @memoized
    def location(self):
        if self.request.GET.get('location_id'):
            return Location.get(self.request.GET.get('location_id'))


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
            startdate=self.datespan.startdate.replace(hour=0, minute=0, second=0),
            enddate=self.datespan.enddate.replace(hour=23, minute=59, second=59),
            visit="''",
            strsd=json_format_date(self.datespan.startdate),
            stred=json_format_date(self.datespan.enddate),
            empty_prd_code='__none__'
        )
        self.config_update(config)
        return config


class IntraHealtMixin(IntraHealthLocationMixin, IntraHealthReportConfigMixin):
    model = None
    data_source = None
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

        self.groups = SQLProduct.objects.filter(domain=self.domain, is_archived=False)
        for group in self.groups:
            if self.model.have_groups:
                header.add_column(DataTablesColumnGroup(group.name,
                    *[columns[j].data_tables_column for j in xrange(1, len(columns))]))
            else:
                header.add_column(DataTablesColumn(group.name))

        return header

    @property
    def rows(self):
        data = self.model.data
        if isinstance(self.model, (NombreData, TauxConsommationData)):
            localizations = sorted(set(key[0] for key in data))
        else:
            localizations = sorted(set(key[1] for key in data))

        rows = []

        formatter = DataFormatter(DictDataFormat(self.model.columns, no_value=self.no_value))
        if isinstance(self.data_source, (NombreData, TauxConsommationData)):
            result = {}
            ppss = set()
            for k, v in data.iteritems():
                ppss.add(k[-2])
                if 'region_id' in self.data_source.config:
                    helper_tuple = (k[2], k[1], k[0])
                else:
                    helper_tuple = (k[1], k[0])

                result[helper_tuple] = v

            if 'region_id' in self.data_source.config:
                result_sum = {}
                for localization in localizations:
                    for pps in ppss:
                        for group in self.groups:
                            if(group.code, localization) in result_sum:
                                r = result_sum[(group.code, localization)]
                                cols = self.data_source.sum_cols
                                for col in cols:
                                    r[col] += result.get((group.code, pps, localization), {col: 0})[col]
                            else:
                                helper_dict = {}
                                for col in self.data_source.sum_cols:
                                    helper_dict[col] = 0
                                helper_dict['district_name'] = localization
                                result_sum[(group.code, localization)] = result.get((group.code,
                                                                                     pps, localization),
                                                                                    helper_dict)
                result = result_sum

            data = dict(formatter.format(result, keys=self.model.keys, group_by=self.model.group_by))
        else:
            data = dict(formatter.format(self.model.data, keys=self.model.keys, group_by=self.model.group_by))

        reversed_map = dict(zip(self.PRODUCT_NAMES.values(), self.PRODUCT_NAMES.keys()))
        for localization in localizations:
            row = [localization]
            for group in self.groups:
                if (group.code, localization) in data:
                    product = data[(group.code, localization)]
                    row.extend([product[p] for p in self.model.col_names])
                elif (self._safe_get(reversed_map, group.code), localization) in data:
                    product = data[(reversed_map[group.code], localization)]
                    row.extend([product[p] for p in self.model.col_names])
                else:
                    row.extend([self.no_value for p in self.model.col_names])
            rows.append(row)
        return rows
