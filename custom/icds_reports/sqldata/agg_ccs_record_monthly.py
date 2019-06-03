from __future__ import absolute_import, division

from __future__ import unicode_literals
from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, SimpleColumn
from sqlagg.filters import BETWEEN, IN, NOT
from sqlagg.sorting import OrderBy

from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn

from corehq.apps.reports.util import get_INFilter_bindparams
from custom.icds_reports.queries import get_test_state_locations_id
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils import percent_num
from custom.icds_reports.utils.mixins import ProgressReportMixIn
from custom.utils.utils import clean_IN_filter_value


class AggCCSRecordMonthlyDataSource(ProgressReportMixIn, IcdsSqlData):
    table_name = 'agg_ccs_record_monthly'

    def __init__(self, config=None, loc_level='state', show_test=False):
        super(AggCCSRecordMonthlyDataSource, self).__init__(config)
        self.loc_key = '%s_id' % loc_level
        self.excluded_states = get_test_state_locations_id(self.domain)
        self.config['excluded_states'] = self.excluded_states
        clean_IN_filter_value(self.config, 'excluded_states')
        self.show_test = show_test

    @property
    def domain(self):
        return self.config['domain']

    @property
    def group_by(self):
        return ['month']

    @property
    def filters(self):
        filters = super(AggCCSRecordMonthlyDataSource, self).filters
        if not self.show_test:
            filters.append(NOT(IN('state_id', get_INFilter_bindparams('excluded_states', self.excluded_states))))
        if 'month' in self.config and self.config['month']:
            filters.append(BETWEEN('month', 'two_before', 'month'))
        return filters

    @property
    def order_by(self):
        return [OrderBy('month')]

    def get_columns(self, filters):
        return [
            DatabaseColumn('month', SimpleColumn('month')),
            AggregateColumn(
                'Percent of pregnant women who are anemic in given month',
                lambda x, y, z: ((x or 0) + (y or 0)) * 100 / float(z or 1),
                [
                    SumColumn('anemic_moderate'),
                    SumColumn('anemic_severe'),
                    SumColumn('pregnant', alias='pregnant')
                ],
                slug='severe_anemic'
            ),
            AggregateColumn(
                'Percent tetanus complete',
                percent_num,
                [
                    SumColumn('tetanus_complete'),
                    AliasColumn('pregnant')
                ],
                slug='tetanus_complete'
            ),
            AggregateColumn(
                'Percent women ANC 1 recieved by deliveryy',
                percent_num,
                [
                    SumColumn('anc1_received_at_delivery'),
                    SumColumn('delivered_in_month', alias='delivered_in_month')
                ],
                slug='anc_1'
            ),
            AggregateColumn(
                'Percent women ANC 2 received by delivery',
                percent_num,
                [
                    SumColumn('anc2_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_2'
            ),
            AggregateColumn(
                'Percent women ANC 3 received by delivery',
                percent_num,
                [
                    SumColumn('anc3_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_3'
            ),
            AggregateColumn(
                'Percent women ANC 4 received by delivery',
                percent_num,
                [
                    SumColumn('anc4_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_4'
            ),
            AggregateColumn(
                'Percent women Resting during pregnancy',
                percent_num,
                [
                    SumColumn('resting_during_pregnancy'),
                    AliasColumn('pregnant')
                ],
                slug='resting'
            ),
            AggregateColumn(
                'Percent eating extra meal during pregnancy',
                percent_num,
                [
                    SumColumn('extra_meal'),
                    AliasColumn('pregnant')
                ],
                slug='extra_meal'
            ),
            AggregateColumn(
                'Percent trimester 3 women Counselled on immediate EBF during home visit',
                percent_num,
                [
                    SumColumn('counsel_immediate_bf'),
                    SumColumn('trimester_3')
                ],
                slug='trimester'
            )
        ]

    @property
    def columns(self):
        return self.get_columns(self.filters)
