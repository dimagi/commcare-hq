from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.columns import SimpleColumn

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from custom.icds_reports.utils.mixins import ExportableMixin


class LadySupervisorExport(ExportableMixin, SqlData):
    title = 'Lady Supervisor'
    table_name = 'agg_ls_monthly'

    @property
    def get_columns_by_loc_level(self):
        return [
            DatabaseColumn('State', SimpleColumn('state_name')),
            DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'),
            DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'),
            DatabaseColumn('Sector Name', SimpleColumn('supervisor_name'), slug='supervisor_name'),
            DatabaseColumn('Name of Lady Supervisor', SimpleColumn('ls_name'), slug='ls_name'),
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
