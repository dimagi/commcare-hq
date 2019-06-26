from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.columns import SimpleColumn

from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.locations.models import  SQLLocation
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ExportableMixin
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED


class TakeHomeRationExport(ExportableMixin, IcdsSqlData):
    title = 'Take Home Ration'
    table_name = 'thr_report_monthly'

    @property
    def get_columns_by_loc_level(self):
        return [
            DatabaseColumn('State', SimpleColumn('state_name')),
            DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'),
            DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'),
            DatabaseColumn('Sector', SimpleColumn('supervisor_name'), slug='supervisor_name'),
            DatabaseColumn('Awc Name', SimpleColumn('awc_name'), slug='awc_name'),
            DatabaseColumn('AWW Name', SimpleColumn('aww_name'), slug='aww_name'),
            DatabaseColumn('AWW Phone No.', SimpleColumn('contact_phone_number'), slug='contact_phone_number'),
            DatabaseColumn('Is launched', SimpleColumn('is_launched'), slug='is_launched'),
            DatabaseColumn('Total No. of Beneficiaries eligible for THR', SimpleColumn('total_thr_candidates'),
                           slug='total_thr_candidates'),
            DatabaseColumn('Total No. of Beneficiaries received THR>21 days in given month',
                           SimpleColumn('thr_given_21_days'), slug='thr_given_21_days'),

            DatabaseColumn('Total No of Pictures taken by AWW', SimpleColumn('thr_distribution_image_count'),
                           slug='thr_distribution_image_count'),
        ]

    def get_excel_data(self, location):
        location_columns = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        excel_rows = []
        headers = []

        for column in self.columns:
            if column.slug != 'is_launched':
                headers.append(column.header)
        excel_rows.append(headers)

        for row in self.get_data():
            row_data = []
            for c in self.columns:
                if c.slug == 'is_launched':
                    continue

                if row['is_launched'] == 'no' and c.slug not in location_columns:
                    row_data.append('AWC Not Launched')
                else:
                    cell = row[c.slug]
                    if not isinstance(cell, dict):
                        if cell is not None:
                            row_data.append(cell)
                        else:
                            row_data.append(DATA_NOT_ENTERED)
                    else:
                        row_data.append(cell['sort_key'] if cell and 'sort_key' in cell else cell)
            excel_rows.append(row_data)

        filters = [['Generated at', india_now()]]
        if location:
            locs = SQLLocation.objects.get(location_id=location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])
        else:
            filters.append(['Location', 'National'])

        if 'month' in self.config:
            date = self.config['month']
            filters.append(['Month', date.strftime("%B")])
            filters.append(['Year', date.year])

        return [
            [
                self.title,
                excel_rows
            ],
            [
                'Export Info',
                filters
            ]
        ]

    @property
    def columns(self):
        return self.get_columns_by_loc_level
