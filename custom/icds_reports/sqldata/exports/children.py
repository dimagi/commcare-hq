from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.base import AliasColumn
from sqlagg.columns import SumWhen, SumColumn, SimpleColumn

from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ExportableMixin
from custom.icds_reports.utils import wasting_severe_column, wasting_moderate_column, \
    wasting_normal_column, stunting_severe_column, stunting_moderate_column, stunting_normal_column, percent, \
    hfa_recorded_in_month_column, wfh_recorded_in_month_column, get_age_condition, phone_number_function


class ChildrenExport(ExportableMixin, IcdsSqlData):
    title = 'Children'
    table_name = 'agg_child_health_monthly'

    def __init__(self, config=None, loc_level=1, show_test=False, beta=False):
        super(ChildrenExport, self).__init__(config, loc_level, show_test, beta)
        self.config.update({
            'age_0': '0',
            'age_6': '6',
            'age_12': '12',
            'age_24': '24',
            'age_36': '36',
            'age_48': '48',
            'age_60': '60',
            'age_72': '72',
        })

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
            AggregateColumn(
                'Weighing efficiency (in month)',
                percent,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'nutrition_status_weighed'}, else_=0,
                        alias='nutrition_status_weighed'
                    ),
                    SumWhen(
                        whens={"age_tranche != :age_72": 'wer_eligible'}, else_=0,
                        alias='wer_eligible'
                    )
                ],
                slug='percent_weight_efficiency'
            ),
            AggregateColumn(
                'Height measurement efficiency (in month)',
                percent,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'height_measured_in_month'}, else_=0,
                        alias='height_measured_in_month_efficiency'
                    ),
                    SumWhen(
                        whens={"age_tranche != :age_72": 'height_eligible'}, else_=0,
                        alias='height_eligible',
                    )
                ],
                slug='height_measurement'
            ),
            DatabaseColumn(
                'Total number of unweighed children (0-5 Years)',
                SumWhen(
                    whens={"age_tranche != :age_72": 'nutrition_status_unweighed'}, else_=0,
                    alias='nutrition_status_unweighed'
                ),
                slug='total_number_unweighed'
            ),
            AggregateColumn(
                'Percentage of severely underweight children',
                percent,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'nutrition_status_severely_underweight'}, else_=0,
                        alias='nutrition_status_severely_underweight'
                    ),
                    AliasColumn('nutrition_status_weighed'),
                ],
                slug='percent_severe_underweight'
            ),
            AggregateColumn(
                'Percentage of moderately underweight children',
                percent,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'nutrition_status_moderately_underweight'}, else_=0,
                        alias='nutrition_status_moderately_underweight'
                    ),
                    AliasColumn('nutrition_status_weighed'),
                ],
                slug='percent_moderate_underweight'
            ),
            AggregateColumn(
                'Percentage of normal weight-for-age children',
                percent,
                [
                    SumWhen(
                        whens={"age_tranche != :age_72": 'nutrition_status_normal'}, else_=0,
                        alias='nutrition_status_normal'
                    ),
                    AliasColumn('nutrition_status_weighed'),
                ],
                slug='percent_normal_weight'
            ),
            AggregateColumn(
                'Percentage of children with severe wasting',
                percent,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): wasting_severe_column(self.beta)},
                        alias='wasting_severe'
                    ),
                    SumWhen(
                        whens={get_age_condition(self.beta): wfh_recorded_in_month_column(self.beta)},
                        alias='weighed_and_height_measured_in_month'
                    ),
                ],
                slug='percent_severe_wasting'
            ),
            AggregateColumn(
                'Percentage of children with moderate wasting',
                percent,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): wasting_moderate_column(self.beta)},
                        alias='wasting_moderate'
                    ),
                    AliasColumn('weighed_and_height_measured_in_month')
                ],
                slug='percent_moderate_wasting'
            ),
            AggregateColumn(
                'Percentage of children with normal weight-for-height',
                percent,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): wasting_normal_column(self.beta)},
                        alias='wasting_normal'
                    ),
                    AliasColumn('weighed_and_height_measured_in_month')
                ],
                slug='percent_normal_wasting'
            ),
            AggregateColumn(
                'Percentage of children with severe stunting',
                percent,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): stunting_severe_column(self.beta)},
                        alias='stunting_severe'
                    ),
                    SumWhen(
                        whens={get_age_condition(self.beta): hfa_recorded_in_month_column(self.beta)},
                        alias='height_measured_in_month'
                    ),
                ],
                slug='percent_severe_stunting'
            ),
            AggregateColumn(
                'Percentage of children with moderate stunting',
                percent,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): stunting_moderate_column(self.beta)},
                        alias='stunting_moderate'
                    ),
                    AliasColumn('height_measured_in_month')
                ],
                slug='percent_moderate_stunting'
            ),
            AggregateColumn(
                'Percentage of children with normal height-for-age',
                percent,
                [
                    SumWhen(
                        whens={get_age_condition(self.beta): stunting_normal_column(self.beta)},
                        alias='stunting_normal'
                    ),
                    AliasColumn('height_measured_in_month')
                ],
                slug='percent_normal_stunting'
            ),
            AggregateColumn(
                'Percent of newborns with low birth weight',
                percent,
                [
                    SumColumn('low_birth_weight_in_month'),
                    SumColumn('weighed_and_born_in_month')
                ],
                slug='newborn_low_birth_weight'
            ),
            AggregateColumn(
                'Percentage of children with completed 1 year immunizations',
                lambda x, y, z: '%.2f%%' % (((x or 0) + (y or 0)) * 100 / float(z or 1)),
                [
                    SumColumn('fully_immunized_on_time'),
                    SumColumn('fully_immunized_late'),
                    SumColumn('fully_immunized_eligible')
                ],
                slug='percent_completed_1year_immunizations'
            ),
            AggregateColumn(
                'Percentage of children breastfed at birth',
                percent,
                [
                    SumColumn('bf_at_birth'),
                    SumColumn('born_in_month')
                ],
                slug='percent_breastfed_at_birth'
            ),
            AggregateColumn(
                'Percentage of children exclusively breastfeeding',
                percent,
                [
                    SumColumn('ebf_in_month'),
                    SumColumn('ebf_eligible')
                ],
                slug='percent_ebf'
            ),
            AggregateColumn(
                'Percentage of children initiated complementary feeding (in the past 30 days)',
                percent,
                [
                    SumColumn('cf_initiation_in_month'),
                    SumColumn('cf_initiation_eligible')
                ],
                slug='percent_initiated_on_cf'
            ),
            AggregateColumn(
                'Percentage of children initiated appropriate complementary feeding',
                percent,
                [
                    SumColumn('cf_in_month'),
                    SumColumn('cf_eligible')
                ],
                slug='percent_appropriate_cf'
            ),
            AggregateColumn(
                'Percentage of children receiving complementary feeding with adequate diet diversity',
                percent,
                [
                    SumColumn('cf_diet_diversity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_diversity'
            ),
            AggregateColumn(
                'Percentage of children receiving complementary feeding with adequate diet quanity',
                percent,
                [
                    SumColumn('cf_diet_quantity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_quanity'
            ),
            AggregateColumn(
                "Percentage of children receiving complementary feeding "
                "with appropriate handwashing before feeding",
                percent,
                [
                    SumColumn('cf_handwashing'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_handwashing_before_feeding'
            ),
        ]
        return columns + agg_columns
