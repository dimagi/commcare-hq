# coding=utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from collections import defaultdict
from sqlagg.columns import SumColumn, MaxColumn, SimpleColumn
from sqlagg.filters import EQ, BETWEEN
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.userreports.util import get_table_name
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from custom.yeksi_naa_reports.utils import YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR, \
    YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT, YEKSI_NAA_REPORTS_LOGISTICIEN
from dateutil.rrule import rrule, MONTHLY
from dateutil.relativedelta import relativedelta
from django.utils.functional import cached_property
from memoized import memoized
from six.moves import range


class YeksiSqlData(SqlData):
    datatables = False
    show_charts = False
    show_total = True
    custom_total_calculate = False
    no_value = {'sort_key': 0, 'html': 0}
    fix_left_col = False

    @property
    def engine_id(self):
        return 'ucr'

    def percent_fn(self, x, y):
        return "{:.2f}%".format(100 * float(x or 0) / float(y or 1))

    @property
    @memoized
    def months(self):
        return [month.date() for month in
                rrule(freq=MONTHLY, dtstart=self.config['startdate'], until=self.config['enddate'])]

    def date_in_selected_date_range(self, date):
        return self.months[0] <= date < self.months[-1] + relativedelta(months=1)

    def get_index_of_month_in_selected_data_range(self, date):
        for index in range(len(self.months)):
            if date < self.months[index] + relativedelta(months=1):
                return index


class VisiteDeLOperateurDataSource(YeksiSqlData):

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        if 'region_id' in self.config and self.config['region_id']:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config and self.config['district_id']:
            filters.append(EQ("district_id", "district_id"))
        elif 'pps_id' in self.config and self.config['pps_id']:
            filters.append(EQ("pps_id", "pps_id"))
        return filters

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR)

    @cached_property
    def loc_id(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_id'
        elif 'region_id' in self.config:
            return 'district_id'
        else:
            return 'region_id'

    @cached_property
    def loc_name(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_name'
        elif 'region_id' in self.config:
            return 'district_name'
        else:
            return 'region_name'

    @property
    def headers(self):
        if self.loc_id == 'pps_id':
            first_row = 'PPS'
        elif self.loc_id == 'district_id':
            first_row = 'District'
        else:
            first_row = 'Region'

        headers = DataTablesHeader(DataTablesColumn(first_row))
        for month in self.months:
            headers.add_column(DataTablesColumn(month.strftime("%B %Y")))
        return headers


class VisiteDeLOperateurPerProductDataSource(YeksiSqlData):

    @property
    def filters(self):
        filters = [BETWEEN("real_date_repeat", "startdate", "enddate")]
        if 'region_id' in self.config and self.config['region_id']:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config and self.config['district_id']:
            filters.append(EQ("district_id", "district_id"))
        elif 'pps_id' in self.config and self.config['pps_id']:
            filters.append(EQ("pps_id", "pps_id"))
        return filters

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT)

    @cached_property
    def loc_id(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_id'
        elif 'region_id' in self.config:
            return 'district_id'
        else:
            return 'region_id'

    @cached_property
    def loc_name(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_name'
        elif 'region_id' in self.config:
            return 'district_name'
        else:
            return 'region_name'

    @property
    def headers(self):
        if self.loc_id == 'pps_id':
            first_row = 'PPS'
        elif self.loc_id == 'district_id':
            first_row = 'District'
        else:
            first_row = 'Region'

        headers = DataTablesHeader(DataTablesColumn(first_row))
        for month in self.months:
            headers.add_column(DataTablesColumn(month.strftime("%B %Y")))
        return headers


class LogisticienDataSource(YeksiSqlData):

    @property
    def filters(self):
        filters = [BETWEEN("opened_on", "startdate", "enddate")]
        if 'region_id' in self.config and self.config['region_id']:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config and self.config['district_id']:
            filters.append(EQ("district_id", "district_id"))
        return filters

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], YEKSI_NAA_REPORTS_LOGISTICIEN)

    @cached_property
    def loc_id(self):
        if 'region_id' in self.config:
            return 'district_id'
        else:
            return 'region_id'

    @cached_property
    def loc_name(self):
        if 'region_id' in self.config:
            return 'district_name'
        else:
            return 'region_name'

    @property
    def headers(self):
        if self.loc_id == 'district_id':
            first_row = 'District'
        else:
            first_row = 'Region'

        headers = DataTablesHeader(DataTablesColumn(first_row))
        for month in self.months:
            headers.add_column(DataTablesColumn(month.strftime("%B %Y")))
        return headers


class AvailabilityData(VisiteDeLOperateurDataSource):
    slug = 'availability'
    comment = 'Availability of the products at the PPS level: how many PPS had ALL products in stock'
    title = 'Availability'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, rows):
        total_row = ['Availability (%)']
        total_numerator = 0
        total_denominator = 0
        if self.loc_id == 'pps_id':
            data = {}
            for i in range(len(self.months)):
                data[i] = {
                    'pps_is_available': sum(
                        pps_data[i + 1] for pps_data in rows if pps_data[i + 1] != 'no data entered'
                    ),
                    'pps_count': sum(1 for pps_data in rows if pps_data[i + 1] != 'no data entered')
                }
                if data[i]['pps_count']:
                    total_row.append(
                        self.percent_fn(
                            data[i]['pps_is_available'],
                            data[i]['pps_count']
                        )
                    )
                else:
                    total_row.append('no data entered')
                total_numerator += data[i]['pps_is_available']
                total_denominator += data[i]['pps_count']

            if total_denominator:
                total_row.append(
                    self.percent_fn(
                        total_numerator,
                        total_denominator
                    )
                )
            else:
                total_row.append('no data entered')
        else:
            for i in range(len(self.months)):
                numerator = 0
                denominator = 0
                for location in rows:
                    numerator += sum(rows[location][i].values())
                    denominator += len(rows[location][i])
                total_numerator += numerator
                total_denominator += denominator
                if denominator:
                    total_row.append(self.percent_fn(numerator, denominator))
                else:
                    total_row.append('no data entered')
            if total_denominator:
                total_row.append(self.percent_fn(total_numerator, total_denominator))
            else:
                total_row.append('no data entered')
        return total_row

    @property
    def group_by(self):
        group_by = ['real_date', 'pps_id', self.loc_name]
        if self.loc_id != 'pps_id':
            group_by.append(self.loc_id)
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn("PPS ID", SimpleColumn('pps_id')),
            DatabaseColumn("Date", SimpleColumn('real_date')),
            DatabaseColumn("Number of PPS with stockout", MaxColumn('pps_is_outstock')),
        ]
        if self.loc_id == 'pps_id':
            columns.append(DatabaseColumn("PPS Name", SimpleColumn('pps_name')))
        elif self.loc_id == 'district_id':
            columns.append(DatabaseColumn("District ID", SimpleColumn('district_id')))
            columns.append(DatabaseColumn("District Name", SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn("Region ID", SimpleColumn('region_id')))
            columns.append(DatabaseColumn("Region Name", SimpleColumn('region_name')))
        return columns

    @property
    def rows(self):
        records = self.get_data()
        data = {}
        loc_names = {}
        if self.loc_id == 'pps_id':
            for record in records:
                if not self.date_in_selected_date_range(record['real_date']):
                    continue
                if record[self.loc_id] not in data:
                    data[record[self.loc_id]] = ['no data entered'] * len(self.months)
                    loc_names[record[self.loc_id]] = record[self.loc_name]
                month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
                data[record[self.loc_id]][month_index] = 0 if record['pps_is_outstock']['html'] == 1 else 1
        else:
            new_data = {}
            for record in records:
                if not self.date_in_selected_date_range(record['real_date']):
                    continue
                if record[self.loc_id] not in data:
                    data[record[self.loc_id]] = []
                    for i in range(len(self.months)):
                        data[record[self.loc_id]].append({})
                    loc_names[record[self.loc_id]] = record[self.loc_name]
                month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
                multiple_rows_per_pps_in_month = data[record[self.loc_id]][month_index].get(record['pps_id'])
                if not multiple_rows_per_pps_in_month or \
                        data[record[self.loc_id]][month_index][record['pps_id']] == 1:
                    data[record[self.loc_id]][month_index][record['pps_id']] = 0 if \
                        record['pps_is_outstock']['html'] == 1 else 1
            for location in data:
                new_data[location] = ['no data entered'] * len(self.months)
                for i in range(len(self.months)):
                    if data[location][i]:
                        new_data[location][i] = self.percent_fn(
                            sum(data[location][i].values()),
                            len(data[location][i]))
            tmp = data
            data = new_data

        new_rows = []
        for loc_id in data:
            row = [loc_names[loc_id]]
            row.extend(data[loc_id])
            numerator = 0
            denominator = 0
            for month in data[loc_id]:
                if month and month != 'no data entered':
                    if self.loc_id == 'pps_id':
                        numerator += float(month)
                    else:
                        numerator += float(month[:-1])
                    denominator += 1
            if denominator:
                if self.loc_id == 'pps_id':
                    row.append("{:.2f}%".format(numerator * 100 / denominator))
                else:
                    row.append("{:.2f}%".format(numerator / denominator))
            else:
                row.append('no data entered')
            new_rows.append(row)
        if self.loc_id == 'pps_id':
            self.total_row = self.calculate_total_row(new_rows)
        else:
            self.total_row = self.calculate_total_row(tmp)
        return new_rows

    @property
    def headers(self):
        headers = super(AvailabilityData, self).headers
        headers.add_column(DataTablesColumn("Avg. Availability"))
        return headers


class LossRateData(VisiteDeLOperateurPerProductDataSource):
    slug = 'loss_rate'
    comment = 'Products lost (excluding expired products)'
    title = 'Products lost (excluding expired products)'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, records):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'loss_amt': 0,
                'pna_final_stock': 0
            }
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if record['loss_amt']:
                data[month_index]['loss_amt'] += record['loss_amt']['html']
            if record['pna_final_stock']:
                data[month_index]['pna_final_stock'] += record['pna_final_stock']['html']

        if 'region_id' in self.config and self.config['region_id']:
            total_row.append('Rate by Region')
        elif 'district_id' in self.config and self.config['district_id']:
            total_row.append('Rate by District')
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row.append('')
        else:
            total_row.append('Rate by Country')
        for monthly_data in data.values():
            total_row.append(
                self.percent_fn(
                    monthly_data['loss_amt'],
                    monthly_data['pna_final_stock']
                )
            )
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', self.loc_id, self.loc_name]

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Total number of PNA lost product", SumColumn('loss_amt')),
            DatabaseColumn("PNA final stock", SumColumn('pna_final_stock')),
        ]
        if self.loc_id == 'pps_id':
            columns.append(DatabaseColumn("PPS ID", SimpleColumn('pps_id')))
            columns.append(DatabaseColumn("PPS Name", SimpleColumn('pps_name')))
        elif self.loc_id == 'district_id':
            columns.append(DatabaseColumn("District ID", SimpleColumn('district_id')))
            columns.append(DatabaseColumn("District Name", SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn("Region ID", SimpleColumn('region_id')))
            columns.append(DatabaseColumn("Region Name", SimpleColumn('region_name')))
        return columns

    @property
    def rows(self):
        records = self.get_data()
        data = {}
        loc_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            if record[self.loc_id] not in data:
                data[record[self.loc_id]] = ['no data entered'] * len(self.months)
                loc_names[record[self.loc_id]] = record[self.loc_name]
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            data[record[self.loc_id]][month_index] = self.percent_fn(
                record['loss_amt']['html'] if record['loss_amt'] else None,
                record['pna_final_stock']['html'] if record['pna_final_stock'] else None)

        new_rows = []
        for loc_id in data:
            row = [loc_names[loc_id]]
            row.extend(data[loc_id])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(records)
        return new_rows

    @property
    def headers(self):
        headers = super(LossRateData, self).headers
        headers.add_column(DataTablesColumn("Target"))
        return headers


class ExpirationRateData(VisiteDeLOperateurPerProductDataSource):
    slug = 'expiration_rate'
    comment = 'Products lost through expiration'
    title = 'Lapse (expiration) rate'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, records):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'expired_pna_valuation': 0,
                'final_pna_stock_valuation': 0
            }
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if record['expired_pna_valuation']:
                data[month_index]['expired_pna_valuation'] += record['expired_pna_valuation']['html']
            if record['final_pna_stock_valuation']:
                data[month_index]['final_pna_stock_valuation'] += record['final_pna_stock_valuation']['html']

        if 'region_id' in self.config and self.config['region_id']:
            total_row.append('Rate by Region')
        elif 'district_id' in self.config and self.config['district_id']:
            total_row.append('Rate by District')
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row.append('')
        else:
            total_row.append('Rate by Country')
        for monthly_data in data.values():
            total_row.append(
                self.percent_fn(
                    monthly_data['expired_pna_valuation'],
                    monthly_data['final_pna_stock_valuation']
                )
            )
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', self.loc_id, self.loc_name]

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Expired products valuation", SumColumn('expired_pna_valuation')),
            DatabaseColumn("Products stock valuation", SumColumn('final_pna_stock_valuation')),
        ]
        if self.loc_id == 'pps_id':
            columns.append(DatabaseColumn("PPS ID", SimpleColumn('pps_id')))
            columns.append(DatabaseColumn("PPS Name", SimpleColumn('pps_name')))
        elif self.loc_id == 'district_id':
            columns.append(DatabaseColumn("District ID", SimpleColumn('district_id')))
            columns.append(DatabaseColumn("District Name", SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn("Region ID", SimpleColumn('region_id')))
            columns.append(DatabaseColumn("Region Name", SimpleColumn('region_name')))
        return columns

    @property
    def rows(self):
        records = self.get_data()
        data = {}
        loc_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            if record[self.loc_id] not in data:
                data[record[self.loc_id]] = ['no data entered'] * len(self.months)
                loc_names[record[self.loc_id]] = record[self.loc_name]
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            data[record[self.loc_id]][month_index] = self.percent_fn(
                record['expired_pna_valuation']['html'] if record['expired_pna_valuation'] else None,
                record['final_pna_stock_valuation']['html'] if record['final_pna_stock_valuation'] else None
            )

        new_rows = []
        for loc_id in data:
            row = [loc_names[loc_id]]
            row.extend(data[loc_id])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(records)
        return new_rows

    @property
    def headers(self):
        headers = super(ExpirationRateData, self).headers
        headers.add_column(DataTablesColumn("Target"))
        return headers


class RecoveryRateByPPSData(VisiteDeLOperateurDataSource):
    slug = 'recovery_rate_by_pps'
    comment = 'Total amount paid vs. owed'
    title = 'Recovery rate by PPS'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, records):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'pps_total_amt_paid': 0,
                'pps_total_amt_owed': 0
            }
        for record in records:
            if not self.date_in_selected_date_range(record['real_date']):
                continue
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
            if record['pps_total_amt_paid']:
                data[month_index]['pps_total_amt_paid'] += record['pps_total_amt_paid']['html']
            if record['pps_total_amt_owed']:
                data[month_index]['pps_total_amt_owed'] += record['pps_total_amt_owed']['html']

        if 'region_id' in self.config and self.config['region_id']:
            total_row.append('Rate by Region')
        elif 'district_id' in self.config and self.config['district_id']:
            total_row.append('Rate by District')
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row.append('')
        else:
            total_row.append('Rate by Country')
        for monthly_data in data.values():
            total_row.append(
                self.percent_fn(
                    monthly_data['pps_total_amt_paid'],
                    monthly_data['pps_total_amt_owed']
                )
            )
        return total_row

    @property
    def group_by(self):
        return ['real_date', 'pps_id', 'pps_name']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("PPS ID", SimpleColumn('pps_id')),
            DatabaseColumn("PPS Name", SimpleColumn('pps_name')),
            DatabaseColumn("Date", SimpleColumn('real_date')),
            DatabaseColumn("Total amount paid by PPS", SumColumn('pps_total_amt_paid')),
            DatabaseColumn("Total amount owed by PPS", SumColumn('pps_total_amt_owed')),
        ]
        return columns

    @property
    def rows(self):
        records = self.get_data()
        data = {}
        pps_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date']):
                continue
            if record['pps_id'] not in data:
                data[record['pps_id']] = ['no data entered'] * len(self.months)
                pps_names[record['pps_id']] = record['pps_name']
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
            data[record['pps_id']][month_index] = self.percent_fn(
                record['pps_total_amt_paid']['html'] if record['pps_total_amt_paid'] else None,
                record['pps_total_amt_owed']['html'] if record['pps_total_amt_owed'] else None
            )

        new_rows = []
        for pps in data:
            row = [pps_names[pps]]
            row.extend(data[pps])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(records)
        return new_rows

    @cached_property
    def loc_id(self):
        return 'pps_id'

    @property
    def headers(self):
        headers = super(RecoveryRateByPPSData, self).headers
        headers.add_column(DataTablesColumn("Target"))
        return headers


class RecoveryRateByDistrictData(LogisticienDataSource):
    slug = 'recovery_rate_by_district'
    comment = 'Total amount paid vs. owed'
    title = 'Recovery rate by District'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, records):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'montant_paye': 0,
                'montant_reel_a_payer': 0
            }
        for record in records:
            if not self.date_in_selected_date_range(record['opened_on']):
                continue
            month_index = self.get_index_of_month_in_selected_data_range(record['opened_on'])
            if record['montant_paye']:
                data[month_index]['montant_paye'] += record['montant_paye']['html']
            if record['montant_reel_a_payer']:
                data[month_index]['montant_reel_a_payer'] += record['montant_reel_a_payer']['html']

        if 'region_id' in self.config and self.config['region_id']:
            total_row.append('Rate by Region')
        elif 'district_id' in self.config and self.config['district_id']:
            total_row.append('Rate by District')
        else:
            total_row.append('Rate by Country')
        for monthly_data in data.values():
            total_row.append(
                self.percent_fn(
                    monthly_data['montant_paye'],
                    monthly_data['montant_reel_a_payer']
                )
            )
        return total_row

    @property
    def group_by(self):
        return ['opened_on', 'district_id', 'district_name']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("District ID", SimpleColumn('district_id')),
            DatabaseColumn("District Name", SimpleColumn('district_name')),
            DatabaseColumn("Date", SimpleColumn('opened_on')),
            DatabaseColumn("Sum of the amounts paid by the district", SumColumn('montant_paye')),
            DatabaseColumn("Total amount owed by the district to PNA", SumColumn('montant_reel_a_payer')),
        ]
        return columns

    @property
    def rows(self):
        records = self.get_data()
        data = {}
        district_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['opened_on']):
                continue
            if record['district_id'] not in data:
                data[record['district_id']] = ['no data entered'] * len(self.months)
                district_names[record['district_id']] = record['district_name']
            month_index = self.get_index_of_month_in_selected_data_range(record['opened_on'])
            data[record['district_id']][month_index] = self.percent_fn(
                record['montant_paye']['html'] if record['montant_paye'] else None,
                record['montant_reel_a_payer']['html'] if record['montant_reel_a_payer'] else None
            )

        new_rows = []
        for district in data:
            row = [district_names[district]]
            row.extend(data[district])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(records)
        return new_rows

    @property
    def headers(self):
        headers = super(RecoveryRateByDistrictData, self).headers
        headers.add_column(DataTablesColumn("Target"))
        return headers


class RuptureRateByPPSData(VisiteDeLOperateurDataSource):
    slug = 'rupture_rate_by_pps'
    comment = '# of products stocked out vs. all products of the PPS'
    title = 'Rupture rate by PPS'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, records):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'nb_products_stockout': 0,
                'pps_nb_products': 0
            }
        for record in records:
            if not self.date_in_selected_date_range(record['real_date']):
                continue
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
            if record['nb_products_stockout']:
                data[month_index]['nb_products_stockout'] += record['nb_products_stockout']['html']
            if record['pps_nb_products']:
                data[month_index]['pps_nb_products'] += record['pps_nb_products']['html']

        if 'region_id' in self.config and self.config['region_id']:
            total_row.append('Rate by Region')
        elif 'district_id' in self.config and self.config['district_id']:
            total_row.append('Rate by District')
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row.append('')
        else:
            total_row.append('Rate by Country')
        for monthly_data in data.values():
            total_row.append(
                self.percent_fn(
                    monthly_data['nb_products_stockout'],
                    monthly_data['pps_nb_products']
                )
            )
        return total_row

    @property
    def group_by(self):
        return ['real_date', 'pps_id', 'pps_name']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("PPS ID", SimpleColumn('pps_id')),
            DatabaseColumn("PPS Name", SimpleColumn('pps_name')),
            DatabaseColumn("Date", SimpleColumn('real_date')),
            DatabaseColumn("Number of stockout products", SumColumn('nb_products_stockout')),
            DatabaseColumn("Number of products in pps", SumColumn('pps_nb_products')),
        ]
        return columns

    @property
    def rows(self):
        records = self.get_data()
        data = {}
        pps_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date']):
                continue
            if record['pps_id'] not in data:
                data[record['pps_id']] = ['no data entered'] * len(self.months)
                pps_names[record['pps_id']] = record['pps_name']
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
            data[record['pps_id']][month_index] = self.percent_fn(
                record['nb_products_stockout']['html'] if record['nb_products_stockout'] else None,
                record['pps_nb_products']['html'] if record['pps_nb_products'] else None
            )

        new_rows = []
        for pps in data:
            row = [pps_names[pps]]
            row.extend(data[pps])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(records)
        return new_rows

    @cached_property
    def loc_id(self):
        return 'pps_id'

    @property
    def headers(self):
        headers = super(RuptureRateByPPSData, self).headers
        headers.add_column(DataTablesColumn("Target"))
        return headers


class SatisfactionRateAfterDeliveryData(VisiteDeLOperateurPerProductDataSource):
    slug = 'satisfaction_rate_after_delivery'
    comment = '% products ordered vs. delivered'
    title = 'Satisfaction Rate after delivery'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, products):
        total_row = ['Total (CFA)']
        for i in range(len(self.months)):
            total_row.append(self.percent_fn(
                sum(
                    products[product_id][i]['numerator'] for product_id in products if
                    products[product_id][i]['denominator']
                ),
                sum(
                    products[product_id][i]['denominator'] for product_id in products if
                    products[product_id][i]['denominator']
                )
            ))
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', 'product_id', 'product_name']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product Name", SimpleColumn('product_name')),
            DatabaseColumn("Quantity of the product delivered", SumColumn('amt_delivered_convenience')),
            DatabaseColumn("Quantity of the product  suggested", SumColumn('ideal_topup')),
        ]
        return columns

    def get_product_satisfaction_rate_per_month(self, records):
        data = defaultdict(list)
        product_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            if record['product_id'] not in data:
                for i in range(len(self.months)):
                    data[record['product_id']].append(defaultdict(int))
                product_names[record['product_id']] = record['product_name']
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if record['amt_delivered_convenience'] and record['ideal_topup']:
                data[record['product_id']][month_index]['amt_delivered_convenience'] += \
                    record['amt_delivered_convenience']['html']
                data[record['product_id']][month_index]['ideal_topup'] += record['ideal_topup']['html']
        return product_names, data

    def parse_satisfaction_rate_to_rows(self, product_names, data):
        rows = []
        for product_id in data:
            row = [product_names[product_id]]
            for i in range(len(self.months)):
                if data[product_id][i]['ideal_topup']:
                    row.append(
                        self.percent_fn(data[product_id][i]['amt_delivered_convenience'],
                                        data[product_id][i]['ideal_topup'])
                    )
                else:
                    row.append('no data entered')
            rows.append(row)
        return rows

    @property
    def rows(self):
        records = self.get_data()
        product_names, data = self.get_product_satisfaction_rate_per_month(records)
        self.total_row = self.calculate_total_row(data)
        return self.parse_satisfaction_rate_to_rows(product_names, data)

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('Product'))
        for month in self.months:
            headers.add_column(DataTablesColumn(month.strftime("%B %Y")))
        return headers


class ValuationOfPNAStockPerProductData(VisiteDeLOperateurPerProductDataSource):
    slug = 'valuation_of_pna_stock_per_product'
    comment = 'Stock value of available PNA products, per product'
    title = 'Valuation of PNA Stock per product'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, records):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'final_pna_stock_valuation': 0
            }
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if record['final_pna_stock_valuation']:
                data[month_index]['final_pna_stock_valuation'] += record['final_pna_stock_valuation']['html']

        total_row.append('Total (CFA)')
        for monthly_data in data.values():
            total_row.append('{:.2f}'.format(monthly_data['final_pna_stock_valuation']))
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', 'product_id', 'product_name']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product Name", SimpleColumn('product_name')),
            DatabaseColumn("Products stock valuation", SumColumn('final_pna_stock_valuation')),
        ]
        return columns

    @property
    def rows(self):
        records = self.get_data()
        data = {}
        product_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            if record['product_id'] not in data:
                data[record['product_id']] = [0] * len(self.months)
                product_names[record['product_id']] = record['product_name']
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if record['final_pna_stock_valuation']:
                data[record['product_id']][month_index] += record['final_pna_stock_valuation']

        new_rows = []
        for product_id in data:
            row = [product_names[product_id]]
            row.extend(['{:.2f}'.format(float(value)) for value in data[product_id]])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(records)
        return new_rows

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('Product'))
        for month in self.months:
            headers.add_column(DataTablesColumn(month.strftime("%B %Y")))
        return headers
