from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, SimpleColumn

from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ExportableMixin
from custom.icds_reports.utils import percent, phone_number_function


class PregnantWomenExport(ExportableMixin, IcdsSqlData):
    title = 'Pregnant Women'
    table_name = 'agg_ccs_record_monthly'

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
            DatabaseColumn('Number of lactating women', SumColumn('lactating'), slug='lactating'),
            DatabaseColumn('Number of pregnant women', SumColumn('pregnant'), slug='pregnant'),
            DatabaseColumn('Number of postnatal women', SumColumn('postnatal'), slug='postnatal'),
            AggregateColumn(
                'Percentage Anemia',
                lambda x, y, z: '%.2f%%' % (((x or 0) + (y or 0)) * 100 / float(z or 1)),
                [
                    SumColumn('anemic_moderate'),
                    SumColumn('anemic_severe'),
                    AliasColumn('pregnant')
                ],
                slug='percent_anemia'
            ),
            AggregateColumn(
                'Percentage Tetanus Completed',
                percent,
                [
                    SumColumn('tetanus_complete'),
                    AliasColumn('pregnant')
                ],
                slug='percent_tetanus_complete'
            ),
            AggregateColumn(
                'Percent women had at least 1 ANC visit by delivery',
                percent,
                [
                    SumColumn('anc1_received_at_delivery'),
                    SumColumn('delivered_in_month')
                ],
                slug='percent_anc1_received_by_delivery'
            ),
            AggregateColumn(
                'Percent women had at least 2 ANC visit by delivery',
                percent,
                [
                    SumColumn('anc2_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc2_received_by_delivery'
            ),
            AggregateColumn(
                'Percent women had at least 3 ANC visit by delivery',
                percent,
                [
                    SumColumn('anc3_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc3_received_by_delivery'
            ),
            AggregateColumn(
                'Percent women had at least 4 ANC visit by delivery',
                percent,
                [
                    SumColumn('anc4_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc4_received_by_delivery'
            ),
            AggregateColumn(
                'Percentage of women resting during pregnancy',
                percent,
                [
                    SumColumn('resting_during_pregnancy'),
                    AliasColumn('pregnant')
                ],
                slug='percent_resting_during_pregnancy'
            ),
            AggregateColumn(
                'Percentage of women eating extra meal during pregnancy',
                percent,
                [
                    SumColumn('extra_meal'),
                    AliasColumn('pregnant')
                ],
                slug='percent_eating_extra_meal_during_pregnancy'
            ),
            AggregateColumn(
                'Percentage of trimester 3 women counselled on immediate breastfeeding',
                percent,
                [
                    SumColumn('counsel_immediate_bf'),
                    SumColumn('trimester_3')
                ],
                slug='percent_trimester_3_women_counselled_on_immediate_bf'
            )
        ]
        return columns + agg_columns
