from __future__ import absolute_import, division

from __future__ import unicode_literals
from sqlagg.base import AliasColumn
from sqlagg.columns import SumWhen, SumColumn, SimpleColumn
from sqlagg.filters import BETWEEN, IN, NOT
from sqlagg.sorting import OrderBy

from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from corehq.apps.reports.util import get_INFilter_bindparams
from custom.icds_reports.queries import get_test_state_locations_id
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ProgressReportMixIn
from custom.icds_reports.utils import percent_num, wasting_severe_column, \
    wasting_moderate_column, wasting_normal_column, stunting_severe_column, stunting_moderate_column, \
    stunting_normal_column, hfa_recorded_in_month_column, wfh_recorded_in_month_column, get_age_condition
from custom.utils.utils import clean_IN_filter_value


class AggChildHealthMonthlyDataSource(ProgressReportMixIn, IcdsSqlData):
    table_name = 'agg_child_health_monthly'

    def __init__(self, config=None, loc_level='state', show_test=False, beta=False):
        super(AggChildHealthMonthlyDataSource, self).__init__(config)
        self.excluded_states = get_test_state_locations_id(self.domain)
        self.loc_key = '%s_id' % loc_level
        self.beta = beta
        self.config.update({
            'age_0': '0',
            'age_6': '6',
            'age_12': '12',
            'age_24': '24',
            'age_36': '36',
            'age_48': '48',
            'age_60': '60',
            'age_72': '72',
            'excluded_states': self.excluded_states
        })
        clean_IN_filter_value(self.config, 'excluded_states')
        self.show_test = show_test

    @property
    def group_by(self):
        return ['month']

    @property
    def domain(self):
        return self.config['domain']

    @property
    def filters(self):
        filters = super(AggChildHealthMonthlyDataSource, self).filters
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
                '% Weighing efficiency (Children <5 weighed)',
                percent_num,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'nutrition_status_weighed'},
                        alias='nutrition_status_weighed'
                    ),
                    SumWhen(
                        whens={"age_tranche != :age_72": 'wer_eligible'},
                        alias='wer_eligible'
                    )
                ],
                slug='status_weighed'
            ),
            AggregateColumn(
                '% Height measurement efficiency (Children <5 measured)',
                percent_num,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'height_measured_in_month'},
                        alias='height_measured_in_month_less_5'
                    ),
                    SumWhen(
                        whens={"age_tranche != :age_72": 'height_eligible'},
                        alias='height_eligible'
                    )
                ],
                slug='status_height_efficiency'
            ),
            DatabaseColumn(
                'Total number Unweighed',
                SumWhen(
                    whens={"age_tranche != :age_72": 'nutrition_status_unweighed'},
                    alias='nutrition_status_unweighed'
                )
            ),
            AggregateColumn(
                'Percent Children severely underweight (weight for age)',
                percent_num,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'nutrition_status_severely_underweight'},
                        alias='nutrition_status_severely_underweight'
                    ),
                    AliasColumn('nutrition_status_weighed')
                ],
                slug='severely_underweight'
            ),
            AggregateColumn(
                'Percent Children moderately underweight (weight for age)',
                percent_num,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'nutrition_status_moderately_underweight'},
                        alias='nutrition_status_moderately_underweight'
                    ),
                    AliasColumn('nutrition_status_weighed')
                ],
                slug='moderately_underweight'
            ),
            AggregateColumn(
                'Percent Children normal (weight for age)',
                percent_num,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'nutrition_status_normal'},
                        alias='nutrition_status_normal'
                    ),
                    AliasColumn('nutrition_status_weighed')
                ],
                slug='status_normal'
            ),
            AggregateColumn(
                'Percent children with severe acute malnutrition (weight-for-height)',
                percent_num,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): wasting_severe_column(self.beta)},
                        alias='wasting_severe'
                    ),
                    SumWhen(
                        whens={get_age_condition(self.beta): wfh_recorded_in_month_column(self.beta)},
                        alias='weighed_and_height_measured_in_month'
                    )
                ],
                slug='wasting_severe'
            ),
            AggregateColumn(
                'Percent children with moderate acute malnutrition (weight-for-height)',
                percent_num,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): wasting_moderate_column(self.beta)},
                        alias='wasting_moderate'
                    ),
                    AliasColumn('weighed_and_height_measured_in_month')
                ],
                slug='wasting_moderate'
            ),
            AggregateColumn(
                'Percent children normal (weight-for-height)',
                percent_num,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): wasting_normal_column(self.beta)},
                        alias='wasting_normal'
                    ),
                    AliasColumn('weighed_and_height_measured_in_month')
                ],
                slug='wasting_normal'
            ),
            AggregateColumn(
                'Percent children with severe stunting (height for age)',
                percent_num,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): stunting_severe_column(self.beta)},
                        alias='zscore_grading_hfa_severe'
                    ),
                    SumWhen(
                        whens={get_age_condition(self.beta): hfa_recorded_in_month_column(self.beta)},
                        alias='height_measured_in_month'
                    )
                ],
                slug='stunting_severe'
            ),
            AggregateColumn(
                'Percent children with moderate stunting (height for age)',
                percent_num,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): stunting_moderate_column(self.beta)},
                        alias='zscore_grading_hfa_moderate'
                    ),
                    AliasColumn('height_measured_in_month')
                ],
                slug='stunting_moderate'
            ),
            AggregateColumn(
                'Percent children with normal (height for age)',
                percent_num,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): stunting_normal_column(self.beta)},
                        alias='zscore_grading_hfa_normal'
                    ),
                    AliasColumn('height_measured_in_month')
                ],
                slug='stunting_normal'
            ),
            AggregateColumn(
                'Percent children immunized with 1st year immunizations',
                lambda x, y, z: ((x or 0) + (y or 0)) * 100 / float(z or 1),
                [
                    SumColumn('fully_immunized_on_time'),
                    SumColumn('fully_immunized_late'),
                    SumColumn('fully_immunized_eligible')
                ],
                slug='fully_immunized'
            ),
            AggregateColumn(
                'Percent Children breastfed at birth',
                percent_num,
                [
                    SumColumn('bf_at_birth'),
                    SumColumn('born_in_month')
                ],
                slug='breastfed_at_birth'
            ),
            AggregateColumn(
                'Percent Children exclusively breastfed',
                percent_num,
                [
                    SumColumn('ebf_in_month'),
                    SumColumn('ebf_eligible')
                ],
                slug='exclusively_breastfed'
            ),
            AggregateColumn(
                'Percent Children initiated appropriate complementary feeding',
                percent_num,
                [
                    SumColumn('cf_initiation_in_month'),
                    SumColumn('cf_initiation_eligible')
                ],
                slug='cf_initiation'
            ),
            AggregateColumn(
                'Perecent children complementary feeding',
                percent_num,
                [
                    SumColumn('cf_in_month'),
                    SumColumn('cf_eligible')
                ],
                slug='complementary_feeding'
            ),
            AggregateColumn(
                'Percentage of children consuming atleast 4 food groups',
                percent_num,
                [
                    SumColumn('cf_diet_diversity'),
                    AliasColumn('cf_eligible')
                ],
                slug='diet_diversity'
            ),
            AggregateColumn(
                'Percentage of children consuming adequate food',
                percent_num,
                [
                    SumColumn('cf_diet_quantity'),
                    AliasColumn('cf_eligible')
                ],
                slug='diet_quantity'
            ),
            AggregateColumn(
                'Percentage of children whose mothers handwash before feeding',
                percent_num,
                [
                    SumColumn('cf_handwashing'),
                    AliasColumn('cf_eligible')
                ],
                slug='handwashing'
            ),
            DatabaseColumn(
                'Children (0 - 28 Days) Seeking Services',
                SumWhen(
                    whens={'age_tranche = :age_0': 'valid_in_month'},
                    alias='zero'
                ),
                slug='zero'
            ),
            DatabaseColumn(
                'Children (28 Days - 6 mo) Seeking Services',
                SumWhen(
                    whens={'age_tranche = :age_6': 'valid_in_month'},
                    alias='one'
                ),
                slug='one'
            ),
            DatabaseColumn(
                'Children (6 mo - 1 year) Seeking Services',
                SumWhen(
                    whens={'age_tranche = :age_12': 'valid_in_month'},
                    alias='two'
                ),
                slug='two'
            ),
            DatabaseColumn(
                'Children (1 year - 3 years) Seeking Services',
                SumWhen(
                    whens={'age_tranche = :age_24 OR age_tranche = :age_36': 'valid_in_month'},
                    alias='three'
                ),
                slug='three'
            ),
            DatabaseColumn(
                'Children (3 years - 6 years) Seeking Services',
                SumWhen(
                    whens={
                        'age_tranche = :age_48 OR age_tranche = :age_60 OR age_tranche = :age_72':
                            'valid_in_month'
                    },
                    alias='four'
                ),
                slug='four'
            ),
            AggregateColumn(
                'Percent of children born in month with low birth weight',
                percent_num,
                [
                    SumColumn('low_birth_weight_in_month'),
                    SumColumn('weighed_and_born_in_month')
                ],
                slug='low_birth_weight'
            )
        ]

    @property
    def columns(self):
        return self.get_columns(self.filters)
