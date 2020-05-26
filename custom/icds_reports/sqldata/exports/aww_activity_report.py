from sqlagg.columns import SimpleColumn

from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ExportableMixin


class AwwActivityExport(ExportableMixin, IcdsSqlData):
    title = 'Aww Activity Report'
    table_name = 'icds_reports_aggregateinactiveaww'

    @property
    def get_columns_by_loc_level(self):
        return [
            DatabaseColumn('State', SimpleColumn('state_name')),
            DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'),
            DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'),
            DatabaseColumn('Supervisor name', SimpleColumn('supervisor_name'), slug='supervisor_name'),
            DatabaseColumn('AWC name', SimpleColumn('awc_name'), slug='awc_name'),
            DatabaseColumn('AWC site code', SimpleColumn('awc_site_code'), slug='awc_site_code'),
            DatabaseColumn('AWC launch date', SimpleColumn('first_submission'), slug='first_submission'),
            DatabaseColumn('Last submission date', SimpleColumn('last_submission'), slug='last_submission'),
            DatabaseColumn('Days since start', SimpleColumn('no_of_days_since_start'),
                           slug='no_of_days_since_start'),
            DatabaseColumn('Days inactive', SimpleColumn('no_of_days_inactive'), slug='no_of_days_inactive')
        ]

    @property
    def columns(self):
        return self.get_columns_by_loc_level
