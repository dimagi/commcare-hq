from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.columns import SimpleColumn

from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ExportableMixin


class LadySupervisorExport(ExportableMixin, IcdsSqlData):
    title = 'Lady Supervisor'
    table_name = 'agg_ls_monthly'

    @property
    def get_columns_by_loc_level(self):
        return [
            DatabaseColumn('State', SimpleColumn('state_name')),
            DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'),
            DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'),
            DatabaseColumn('Sector Name', SimpleColumn('supervisor_name'), slug='supervisor_name'),
            DatabaseColumn('Lady Supervisor User ID', SimpleColumn('supervisor_site_code'),
                           slug='supervisor_site_code'),
            DatabaseColumn('Total No. of AWCs visited', SimpleColumn('awc_visits'), slug='awc_visits'),
            DatabaseColumn(
                'Total No. of Beneficiaries Visited',
                SimpleColumn('beneficiary_vists'),
                slug='beneficiary_vists'
            ),
            DatabaseColumn('Total No. of VHNDs observed', SimpleColumn('vhnd_observed'), slug='vhnd_observed'),
        ]

    @property
    def columns(self):
        return self.get_columns_by_loc_level
