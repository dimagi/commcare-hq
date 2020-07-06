import datetime
from sqlagg.columns import SumColumn, SimpleColumn

from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ExportableMixin, NUM_LAUNCHED_AWCS, NUM_OF_DAYS_AWC_WAS_OPEN
from custom.icds_reports.utils import phone_number_function


class SystemUsageExport(ExportableMixin, IcdsSqlData):
    title = 'System Usage'

    def __init__(self, config=None, loc_level=1, show_test=False, beta=False):
        super(SystemUsageExport, self).__init__(config, loc_level, show_test, beta)
        self.table_name = 'system_usage_report_view'

    @property
    def get_columns_by_loc_level(self):
        columns = [
            DatabaseColumn('State', SimpleColumn('state_name'))
        ]
        if self.loc_level > 1:
            columns.append(DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'))
        if self.loc_level > 2:
            columns.append(DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'))
        if self.loc_level > 3:
            columns.append(DatabaseColumn('Supervisor', SimpleColumn('supervisor_name'), slug='supervisor_name'))
        if self.loc_level > 4:
            columns.append(DatabaseColumn('AWC', SimpleColumn('awc_name'), slug='awc_name'))
            columns.append(DatabaseColumn(
                'AWC Site Code',
                SimpleColumn('awc_site_code'),
                slug='awc_site_code')
            )
            columns.append(DatabaseColumn(
                'AWW Phone Number',
                SimpleColumn('contact_phone_number'),
                format_fn=phone_number_function,
                slug='contact_phone_number')
            )
        return columns

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        agg_columns = [
            DatabaseColumn(
                NUM_OF_DAYS_AWC_WAS_OPEN,
                SumColumn('awc_days_open'),
                format_fn=lambda x: (x or 0) if self.loc_level > 4 else "Applicable at only AWC level",
                slug='num_awc_open'
            ),
            DatabaseColumn(
                NUM_LAUNCHED_AWCS,
                SumColumn('num_launched_awcs'),
                format_fn=lambda x: (x or 0),
                slug='num_launched_awcs'
            ),
            DatabaseColumn(
                'Number of household registration forms',
                SumColumn('usage_num_hh_reg'),
                slug='num_hh_reg_forms'
            ),
            DatabaseColumn(
                'Number of add pregnancy forms',
                SumColumn('usage_num_add_pregnancy'),
                slug='num_add_pregnancy_forms'
            ),
            DatabaseColumn(
                'Number of birth preparedness forms',
                SumColumn('usage_num_bp_tri'),
                slug='usage_num_bp_tri'
            ),
            DatabaseColumn(
                'Number of delivery forms',
                SumColumn('usage_num_delivery'),
                slug='num_delivery_forms'
            ),
            DatabaseColumn('Number of PNC forms', SumColumn('usage_num_pnc'), slug='num_pnc_forms'),
            DatabaseColumn(
                'Number of exclusive breastfeeding forms',
                SumColumn('usage_num_ebf'),
                slug='num_ebf_forms'
            ),
            DatabaseColumn(
                'Number of complementary feeding forms',
                SumColumn('usage_num_cf'),
                slug='num_cf_forms'
            ),
            DatabaseColumn(
                'Number of growth monitoring forms',
                SumColumn('usage_num_gmp'),
                slug='num_gmp_forms'
            ),
            DatabaseColumn(
                'Number of take home rations forms',
                SumColumn('usage_num_thr'),
                slug='num_thr_forms'
            ),
            DatabaseColumn(
                'Number of due list forms',
                SumColumn('usage_num_due_list_ccs_and_child_health'),
                slug='usage_num_due_list_ccs_and_child_health'
            )
        ]
        # adding this field to reports from jan 2020
        if self.config['month'] >= datetime.date(2020, 1, 1):
            agg_columns.append(DatabaseColumn(
                'Number of launched LSs',
                SumColumn('num_supervisor_launched'),
                format_fn=lambda x: (x or 0) if self.loc_level < 5 else "Not applicable at AWC level",
                slug='num_supervisor_launched')
            )
        return columns + agg_columns
