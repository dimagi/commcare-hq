# coding=utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

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
        if self.loc_id == 'pps_id':
            data = {}
            for i in range(len(self.months)):
                data[i] = {
                    'pps_is_outstock': 0,
                    'pps_count': 0
                }
            for row in rows:
                if self.months[0] <= row['real_date'] < self.months[-1] + relativedelta(months=1):
                    for i in range(len(self.months)):
                        if row['real_date'] < self.months[i] + relativedelta(months=1):
                            if row['pps_is_outstock']:
                                data[i]['pps_is_outstock'] += row['pps_is_outstock']['html']
                            if row['pps_count']:
                                data[i]['pps_count'] += row['pps_count']['html']
                            break

            for monthly_data in data.values():
                total_row.append(
                    self.percent_fn(
                        monthly_data['pps_is_outstock'],
                        monthly_data['pps_count']
                    )
                )
            if data:
                total_row.append(
                    "{:.2f}%".format(
                        sum([100 * float(month['pps_is_outstock'] or 0) / float(month['pps_count'] or 1)
                             for month in data.values()
                             if month and month != 'no data entered'])
                        / len(data)
                    )
                )
        else:
            for i in range(len(self.months)):
                nominator = 0
                denominator = 0
                for location in rows:
                    nominator += sum(rows[location][i].values())
                    denominator += len(rows[location][i])
                total_row.append(
                    self.percent_fn(nominator, denominator)
                )
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
        rows = self.get_data()
        data = {}
        loc_names = {}
        if self.loc_id == 'pps_id':
            for row in rows:
                if row['real_date'] < self.months[0] or \
                        self.months[-1] + relativedelta(months=1) <= row['real_date']:
                    continue
                if row[self.loc_id] not in data:
                    data[row[self.loc_id]] = ['no data entered'] * len(self.months)
                    loc_names[row[self.loc_id]] = row[self.loc_name]
                for i in range(len(self.months)):
                    if row['real_date'] < self.months[i] + relativedelta(months=1):
                        data[row[self.loc_id]][i] = 0 if row['pps_is_outstock']['html'] == 1 else 1
                        break
        else:
            new_data = {}
            for row in rows:
                if row['real_date'] < self.months[0] or \
                        self.months[-1] + relativedelta(months=1) <= row['real_date']:
                    continue
                if row[self.loc_id] not in data:
                    data[row[self.loc_id]] = [{}] * len(self.months)
                    loc_names[row[self.loc_id]] = row[self.loc_name]
                for i in range(len(self.months)):
                    if row['real_date'] < self.months[i] + relativedelta(months=1):
                        if data[row[self.loc_id]][i].get(row['pps_id']) and \
                                data[row[self.loc_id]][i][row['pps_id']] == 0:
                            data[row[self.loc_id]][i][row['pps_id']] = 0 if row['pps_is_outstock']['html'] == 1 \
                                else 1
                        else:
                            data[row[self.loc_id]][i][row['pps_id']] = 0 if row['pps_is_outstock']['html'] == 1 \
                                else 1
                        break
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
            row.append("{:.2f}%".format(
                sum([float(month[:-1]) for month in data[loc_id] if month and month != 'no data entered'])
                / len(data[loc_id])
            ))
            new_rows.append(row)
        if self.loc_id == 'pps_id':
            self.total_row = self.calculate_total_row(rows)
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

    def calculate_total_row(self, rows):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'loss_amt': 0,
                'pna_final_stock': 0
            }
        for row in rows:
            if self.months[0] <= row['real_date_repeat'] < self.months[-1] + relativedelta(months=1):
                for i in range(len(self.months)):
                    if row['real_date_repeat'] < self.months[i] + relativedelta(months=1):
                        if row['loss_amt']:
                            data[i]['loss_amt'] += row['loss_amt']['html']
                        if row['pna_final_stock']:
                            data[i]['pna_final_stock'] += row['pna_final_stock']['html']
                        break

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
        rows = self.get_data()
        data = {}
        loc_names = {}
        for row in rows:
            if self.months[0] <= row['real_date_repeat'] < self.months[-1] + relativedelta(months=1):
                if row[self.loc_id] not in data:
                    data[row[self.loc_id]] = ['no data entered'] * len(self.months)
                    loc_names[row[self.loc_id]] = row[self.loc_name]
                for i in range(len(self.months)):
                    if row['real_date_repeat'] < self.months[i] + relativedelta(months=1):
                        data[row[self.loc_id]][i] = self.percent_fn(
                            row['loss_amt']['html'] if row['loss_amt'] else None,
                            row['pna_final_stock']['html'] if row['pna_final_stock'] else None)
                        break

        new_rows = []
        for loc_id in data:
            row = [loc_names[loc_id]]
            row.extend(data[loc_id])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(rows)
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

    def calculate_total_row(self, rows):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'expired_pna_valuation': 0,
                'final_pna_stock_valuation': 0
            }
        for row in rows:
            if self.months[0] <= row['real_date_repeat'] < self.months[-1] + relativedelta(months=1):
                for i in range(len(self.months)):
                    if row['real_date_repeat'] < self.months[i] + relativedelta(months=1):
                        if row['expired_pna_valuation']:
                            data[i]['expired_pna_valuation'] += row['expired_pna_valuation']['html']
                        if row['final_pna_stock_valuation']:
                            data[i]['final_pna_stock_valuation'] += row['final_pna_stock_valuation']['html']
                        break

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
        rows = self.get_data()
        data = {}
        loc_names = {}
        for row in rows:
            if self.months[0] <= row['real_date_repeat'] < self.months[-1] + relativedelta(months=1):
                if row[self.loc_id] not in data:
                    data[row[self.loc_id]] = ['no data entered'] * len(self.months)
                    loc_names[row[self.loc_id]] = row[self.loc_name]
                for i in range(len(self.months)):
                    if row['real_date_repeat'] < self.months[i] + relativedelta(months=1):
                        data[row[self.loc_id]][i] = self.percent_fn(
                            row['expired_pna_valuation']['html'] if row['expired_pna_valuation'] else None,
                            row['final_pna_stock_valuation']['html'] if row['final_pna_stock_valuation'] else None)
                        break

        new_rows = []
        for loc_id in data:
            row = [loc_names[loc_id]]
            row.extend(data[loc_id])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(rows)
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

    def calculate_total_row(self, rows):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'pps_total_amt_paid': 0,
                'pps_total_amt_owed': 0
            }
        for row in rows:
            if self.months[0] <= row['real_date'] < self.months[-1] + relativedelta(months=1):
                for i in range(len(self.months)):
                    if row['real_date'] < self.months[i] + relativedelta(months=1):
                        if row['pps_total_amt_paid']:
                            data[i]['pps_total_amt_paid'] += row['pps_total_amt_paid']['html']
                        if row['pps_total_amt_owed']:
                            data[i]['pps_total_amt_owed'] += row['pps_total_amt_owed']['html']
                        break

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
        rows = self.get_data()
        data = {}
        pps_names = {}
        for row in rows:
            if self.months[0] <= row['real_date'] < self.months[-1] + relativedelta(months=1):
                if row['pps_id'] not in data:
                    data[row['pps_id']] = ['no data entered'] * len(self.months)
                    pps_names[row['pps_id']] = row['pps_name']
                for i in range(len(self.months)):
                    if row['real_date'] < self.months[i] + relativedelta(months=1):
                        data[row['pps_id']][i] = self.percent_fn(
                            row['pps_total_amt_paid']['html'] if row['pps_total_amt_paid'] else None,
                            row['pps_total_amt_owed']['html'] if row['pps_total_amt_owed'] else None)
                        break

        new_rows = []
        for pps in data:
            row = [pps_names[pps]]
            row.extend(data[pps])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(rows)
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

    def calculate_total_row(self, rows):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'montant_paye': 0,
                'montant_reel_a_payer': 0
            }
        for row in rows:
            if self.months[0] <= row['opened_on'] < self.months[-1] + relativedelta(months=1):
                for i in range(len(self.months)):
                    if row['opened_on'] < self.months[i] + relativedelta(months=1):
                        if row['montant_paye']:
                            data[i]['montant_paye'] += row['montant_paye']['html']
                        if row['montant_reel_a_payer']:
                            data[i]['montant_reel_a_payer'] += row['montant_reel_a_payer']['html']
                        break

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
        rows = self.get_data()
        data = {}
        district_names = {}
        for row in rows:
            if self.months[0] <= row['opened_on'] < self.months[-1] + relativedelta(months=1):
                if row['district_id'] not in data:
                    data[row['district_id']] = ['no data entered'] * len(self.months)
                    district_names[row['district_id']] = row['district_name']
                for i in range(len(self.months)):
                    if row['opened_on'] < self.months[i] + relativedelta(months=1):
                        data[row['district_id']][i] = self.percent_fn(
                            row['montant_paye']['html'] if row['montant_paye'] else None,
                            row['montant_reel_a_payer']['html'] if row['montant_reel_a_payer'] else None)
                        break

        new_rows = []
        for district in data:
            row = [district_names[district]]
            row.extend(data[district])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(rows)
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

    def calculate_total_row(self, rows):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'nb_products_stockout': 0,
                'pps_nb_products': 0
            }
        for row in rows:
            if self.months[0] <= row['real_date'] < self.months[-1] + relativedelta(months=1):
                for i in range(len(self.months)):
                    if row['real_date'] < self.months[i] + relativedelta(months=1):
                        if row['nb_products_stockout']:
                            data[i]['nb_products_stockout'] += row['nb_products_stockout']['html']
                        if row['pps_nb_products']:
                            data[i]['pps_nb_products'] += row['pps_nb_products']['html']
                        break

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
        rows = self.get_data()
        data = {}
        pps_names = {}
        for row in rows:
            if self.months[0] <= row['real_date'] < self.months[-1] + relativedelta(months=1):
                if row['pps_id'] not in data:
                    data[row['pps_id']] = ['no data entered'] * len(self.months)
                    pps_names[row['pps_id']] = row['pps_name']
                for i in range(len(self.months)):
                    if row['real_date'] < self.months[i] + relativedelta(months=1):
                        data[row['pps_id']][i] = self.percent_fn(
                            row['nb_products_stockout']['html'] if row['nb_products_stockout'] else None,
                            row['pps_nb_products']['html'] if row['pps_nb_products'] else None)
                        break

        new_rows = []
        for pps in data:
            row = [pps_names[pps]]
            row.extend(data[pps])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(rows)
        return new_rows

    @cached_property
    def loc_id(self):
        return 'pps_id'

    @property
    def headers(self):
        headers = super(RuptureRateByPPSData, self).headers
        headers.add_column(DataTablesColumn("Target"))
        return headers


class ValuationOfPNAStockPerProductData(VisiteDeLOperateurPerProductDataSource):
    slug = 'valuation_of_pna_stock_per_product'
    comment = 'Stock value of available PNA products, per product'
    title = 'Valuation of PNA Stock per product'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, rows):
        total_row = []
        data = {}
        for i in range(len(self.months)):
            data[i] = {
                'final_pna_stock_valuation': 0
            }
        for row in rows:
            if self.months[0] <= row['real_date_repeat'] < self.months[-1] + relativedelta(months=1):
                for i in range(len(self.months)):
                    if row['real_date_repeat'] < self.months[i] + relativedelta(months=1):
                        if row['final_pna_stock_valuation']:
                            data[i]['final_pna_stock_valuation'] += row['final_pna_stock_valuation']['html']
                        break

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
        rows = self.get_data()
        data = {}
        product_names = {}
        for row in rows:
            if self.months[0] <= row['real_date_repeat'] < self.months[-1] + relativedelta(months=1):
                if row['product_id'] not in data:
                    data[row['product_id']] = [0] * len(self.months)
                    product_names[row['product_id']] = row['product_name']
                for i in range(len(self.months)):
                    if row['real_date_repeat'] < self.months[i] + relativedelta(months=1):
                        if row['final_pna_stock_valuation']:
                            data[row['product_id']][i] += row['final_pna_stock_valuation']
                        break

        new_rows = []
        for product_id in data:
            row = [product_names[product_id]]
            row.extend(['{:.2f}'.format(float(value)) for value in data[product_id]])
            new_rows.append(row)
        self.total_row = self.calculate_total_row(rows)
        return new_rows

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('Product'))
        for month in self.months:
            headers.add_column(DataTablesColumn(month.strftime("%B %Y")))
        return headers
