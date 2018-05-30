from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.columns import SimpleColumn, CountUniqueColumn
from sqlagg.filters import EQ, OR, IN, GTE

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.userreports.util import get_table_name
from custom.utils.utils import clean_IN_filter_value


class ChildHealthMonthlyURC(SqlData):
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None):
        config.update({
            'sc': 'sc',
            'st': 'st',
            'obc': 'obc',
            'other': 'other',
            'one': 1,
            'male': 'M',
            'female': 'F',
            'age_48': '48',
            'age_60': '60',
            'age_72': '72',
            'twentyone': 21,
            'yes': 'yes'
        })
        self.awcs = config['awc_id']
        super(ChildHealthMonthlyURC, self).__init__(config)

    @property
    def filter_values(self):
        clean_IN_filter_value(self.config, 'awc_id')
        return self.config

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'static-child_cases_monthly_tableau_v2')

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
    def order_by(self):
        return []

    @property
    def columns(self):
        return [
            DatabaseColumn('awc_id', SimpleColumn('awc_id')),
            DatabaseColumn('pre_sc_boys_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_sc_boys_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('caste', 'sc'),
                    EQ('sex', 'male'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_sc_girls_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_sc_girls_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('caste', 'sc'),
                    EQ('sex', 'female'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_st_boys_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_st_boys_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('caste', 'st'),
                    EQ('sex', 'male'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_st_girls_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_st_girls_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('caste', 'st'),
                    EQ('sex', 'female'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_obc_boys_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_obc_boys_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('caste', 'obc'),
                    EQ('sex', 'male'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_obc_girls_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_obc_girls_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('caste', 'obc'),
                    EQ('sex', 'female'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_general_boys_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_general_boys_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('caste', 'other'),
                    EQ('sex', 'male'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_general_girls_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_general_girls_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('caste', 'other'),
                    EQ('sex', 'female'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_total_boys_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_total_boys_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('sex', 'male'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_total_girls_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_total_girls_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('sex', 'female'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                ]
            )),
            DatabaseColumn('pre_minority_boys_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_minority_boys_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('sex', 'male'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                    EQ('minority', 'yes'),
                ]
            )),
            DatabaseColumn('pre_minority_girls_36_72', CountUniqueColumn(
                'doc_id',
                alias='pre_minority_girls_36_72',
                filters=self.filters + [
                    GTE('pse_days_attended', 'twentyone'),
                    EQ('sex', 'female'),
                    OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72'),
                    ]),
                    EQ('minority', 'yes'),
                ]
            ))
        ]
