from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.columns import SimpleColumn, CountUniqueColumn
from sqlagg.filters import EQ, IN, GT

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.userreports.util import get_table_name
from custom.utils.utils import clean_IN_filter_value


class CcsRecordMonthlyURC(SqlData):
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None):
        config.update({
            'sc': 'sc',
            'st': 'st',
            'obc': 'obc',
            'other': 'other',
            'one': 1,
            'yes': 'yes',
            'twentyone': 21
        })
        self.awcs = config['awc_id']
        super(CcsRecordMonthlyURC, self).__init__(config)

    @property
    def filter_values(self):
        clean_IN_filter_value(self.config, 'awc_id')
        return self.config

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'static-ccs_record_cases_monthly_tableau_v2')

    @property
    def filters(self):
        return [
            IN('awc_id', get_INFilter_bindparams('awc_id', self.awcs)),
            EQ('month', 'month')
        ]

    @property
    def group_by(self):
        return ['awc_id']

    @property
    def columns(self):
        return [
            DatabaseColumn('awc_id', SimpleColumn('awc_id')),
            DatabaseColumn('sc_pregnant', CountUniqueColumn(
                'doc_id',
                alias='sc_pregnant',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('caste', 'sc'),
                    EQ('pregnant', 'one'),
                ]
            )),
            DatabaseColumn('st_pregnant', CountUniqueColumn(
                'doc_id',
                alias='st_pregnant',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('caste', 'st'),
                    EQ('pregnant', 'one'),
                ]
            )),
            DatabaseColumn('obc_pregnant', CountUniqueColumn(
                'doc_id',
                alias='obc_pregnant',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('caste', 'obc'),
                    EQ('pregnant', 'one'),
                ]
            )),
            DatabaseColumn('general_pregnant', CountUniqueColumn(
                'doc_id',
                alias='general_pregnant',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('caste', 'other'),
                    EQ('pregnant', 'one'),
                ]
            )),
            DatabaseColumn('total_pregnant', CountUniqueColumn(
                'doc_id',
                alias='total_pregnant',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('pregnant', 'one'),
                ]
            )),
            DatabaseColumn('sc_lactating', CountUniqueColumn(
                'doc_id',
                alias='sc_lactating',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('caste', 'sc'),
                    EQ('lactating', 'one'),
                ]
            )),
            DatabaseColumn('st_lactating', CountUniqueColumn(
                'doc_id',
                alias='st_lactating',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('caste', 'st'),
                    EQ('lactating', 'one'),
                ]
            )),
            DatabaseColumn('obc_lactating', CountUniqueColumn(
                'doc_id',
                alias='obc_lactating',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('caste', 'obc'),
                    EQ('lactating', 'one'),
                ]
            )),
            DatabaseColumn('general_lactating', CountUniqueColumn(
                'doc_id',
                alias='general_lactating',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('caste', 'other'),
                    EQ('lactating', 'one'),
                ]
            )),
            DatabaseColumn('total_lactating', CountUniqueColumn(
                'doc_id',
                alias='total_lactating',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('lactating', 'one'),
                ]
            )),
            DatabaseColumn('minority_pregnant', CountUniqueColumn(
                'doc_id',
                alias='minority_pregnant',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('pregnant', 'one'),
                    EQ('minority', 'yes'),
                ]
            )),
            DatabaseColumn('minority_lactating', CountUniqueColumn(
                'doc_id',
                alias='minority_lactating',
                filters=self.filters + [
                    GT('num_rations_distributed', 'twentyone'),
                    EQ('lactating', 'one'),
                    EQ('minority', 'yes'),
                ]
            )),
        ]
