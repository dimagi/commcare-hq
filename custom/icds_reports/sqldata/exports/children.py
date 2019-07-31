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
                    SumColumn('low_birth_weight_in_month',
                              alias='low_birth_weight_in_month'),
                    SumColumn('weighed_and_born_in_month',
                              alias='weighed_and_born_in_month')
                ],
                slug='newborn_low_birth_weight'
            ),
            AggregateColumn(
                'Percentage of children with completed 1 year immunizations',
                lambda x, y, z: '%.2f%%' % (((x or 0) + (y or 0)) * 100 / float(z or 1)),
                [
                    SumColumn('fully_immunized_on_time',
                              alias='fully_immunized_on_time'),
                    SumColumn('fully_immunized_late',
                              alias='fully_immunized_late'),
                    SumColumn('fully_immunized_eligible',
                              alias='fully_immunized_eligible')
                ],
                slug='percent_completed_1year_immunizations'
            ),
            AggregateColumn(
                'Percentage of children breastfed at birth',
                percent,
                [
                    SumColumn('bf_at_birth',
                              alias='bf_at_birth'),
                    SumColumn('born_in_month',
                              alias='born_in_month')
                ],
                slug='percent_breastfed_at_birth'
            ),
            AggregateColumn(
                'Percentage of children exclusively breastfeeding',
                percent,
                [
                    SumColumn('ebf_in_month',
                              alias='ebf_in_month'),
                    SumColumn('ebf_eligible',
                              alias='ebf_eligible')
                ],
                slug='percent_ebf'
            ),
            AggregateColumn(
                'Percentage of children initiated complementary feeding (in the past 30 days)',
                percent,
                [
                    SumColumn('cf_initiation_in_month',
                              alias='cf_initiation_in_month'),
                    SumColumn('cf_initiation_eligible',
                              alias='cf_initiation_eligible')
                ],
                slug='percent_initiated_on_cf'
            ),
            AggregateColumn(
                'Percentage of children initiated appropriate complementary feeding',
                percent,
                [
                    SumColumn('cf_in_month',
                              alias='cf_in_month'),
                    SumColumn('cf_eligible',
                              alias='cf_eligible')
                ],
                slug='percent_appropriate_cf'
            ),
            AggregateColumn(
                'Percentage of children receiving complementary feeding with adequate diet diversity',
                percent,
                [
                    SumColumn('cf_diet_diversity',
                              alias='cf_diet_diversity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_diversity'
            ),
            AggregateColumn(
                'Percentage of children receiving complementary feeding with adequate diet quantity',
                percent,
                [
                    SumColumn('cf_diet_quantity',
                              alias='cf_diet_quantity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_quanity'
            ),
            AggregateColumn(
                "Percentage of children receiving complementary feeding "
                "with appropriate handwashing before feeding",
                percent,
                [
                    SumColumn('cf_handwashing',
                              alias='cf_handwashing'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_handwashing_before_feeding'
            ),
        ]

        if self.beta:
            agg_columns.insert(0, DatabaseColumn('Total no. of children weighed',
                                                 AliasColumn('nutrition_status_weighed'),
                                                 slug='nutrition_status_weighed'))
            agg_columns.insert(1, DatabaseColumn('Total no. of children eligible to be weighed',
                                                 AliasColumn('wer_eligible'),
                                             slug='wer_eligible'))

            agg_columns.insert(3, DatabaseColumn('Total no. of children whose height was measured',
                                                 AliasColumn('height_measured_in_month_efficiency'),
                                                 slug='height_measured_in_month_efficiency'))
            agg_columns.insert(4, DatabaseColumn('Total no. of children  eligible for measuring height',
                                                 AliasColumn('height_eligible'),
                                                 slug='height_eligible'))


            agg_columns.insert(7, DatabaseColumn('No. of severely underweight children',
                                                 AliasColumn('nutrition_status_severely_underweight'),
                                                 slug='nutrition_status_severely_underweight'))
            agg_columns.insert(8, DatabaseColumn('Total No. of children weighed',
                                                 AliasColumn('nutrition_status_weighed'),
                                                 slug='nutrition_status_weighed'))

            agg_columns.insert(10, DatabaseColumn('No. of moderately underweight children ',
                                                 AliasColumn('nutrition_status_moderately_underweight'),
                                                 slug='nutrition_status_moderately_underweight'))
            agg_columns.insert(11, DatabaseColumn('Total No. of children weighed',
                                                 AliasColumn('nutrition_status_weighed'),
                                                 slug='nutrition_status_weighed'))

            agg_columns.insert(13, DatabaseColumn('No. of  children with normal weight for age',
                                                 AliasColumn('nutrition_status_normal'),
                                                 slug='nutrition_status_normal'))
            agg_columns.insert(14, DatabaseColumn('Total No. of children weighed',
                                                 AliasColumn('nutrition_status_weighed'),
                                                 slug='nutrition_status_weighed'))

            agg_columns.insert(16, DatabaseColumn('No. of Children with severe wasting',
                                                 AliasColumn('wasting_severe'),
                                                 slug='wasting_severe'))
            agg_columns.insert(17, DatabaseColumn('Total number of children whose height and weight is measured',
                                                 AliasColumn('weighed_and_height_measured_in_month'),
                                                 slug='weighed_and_height_measured_in_month'))

            agg_columns.insert(19, DatabaseColumn('No. of moderately wasted children',
                                                 AliasColumn('wasting_moderate'),
                                                 slug='wasting_moderate'))
            agg_columns.insert(20, DatabaseColumn('Total number of children whose height and weight is measured',
                                                 AliasColumn('weighed_and_height_measured_in_month'),
                                                 slug='weighed_and_height_measured_in_month'))

            agg_columns.insert(22, DatabaseColumn('No. of children with normal weight-for-height',
                                                 AliasColumn('wasting_normal'),
                                                 slug='wasting_normal'))
            agg_columns.insert(23, DatabaseColumn('Total no. of children  whose height and weight is measured',
                                                 AliasColumn('weighed_and_height_measured_in_month'),
                                                 slug='weighed_and_height_measured_in_month'))

            agg_columns.insert(25, DatabaseColumn('No. of severely stunted children',
                                                 AliasColumn('stunting_severe'),
                                                 slug='stunting_severe'))
            agg_columns.insert(26, DatabaseColumn('Total no. of children whose height has been measured',
                                                 AliasColumn('height_measured_in_month'),
                                                 slug='height_measured_in_month'))

            agg_columns.insert(28, DatabaseColumn('No. of moderately stunted children',
                                                 AliasColumn('stunting_moderate'),
                                                 slug='stunting_moderate'))
            agg_columns.insert(29, DatabaseColumn('Total no. of children whose height has been measured',
                                                 AliasColumn('height_measured_in_month'),
                                                 slug='height_measured_in_month'))

            agg_columns.insert(31, DatabaseColumn('No. of children with normal height for age',
                                                 AliasColumn('stunting_normal'),
                                                 slug='stunting_normal'))
            agg_columns.insert(32, DatabaseColumn('Total no. of children whose height has been measured',
                                                 AliasColumn('height_measured_in_month'),
                                                 slug='height_measured_in_month'))

            agg_columns.insert(34, DatabaseColumn('No. of newborns with low birth weight',
                                                 AliasColumn('low_birth_weight_in_month'),
                                                 slug='low_birth_weight_in_month'))
            agg_columns.insert(35, DatabaseColumn('Total no. of children born and weighed in the current month',
                                                 AliasColumn('weighed_and_born_in_month'),
                                                 slug='weighed_and_born_in_month'))

            agg_columns.insert(37,  AggregateColumn('No. of children completed 1 year immunization',
                                                    lambda x, y: ((x or 0) + (y or 0)), [
                                                        AliasColumn('fully_immunized_on_time'),
                                                        AliasColumn('fully_immunized_late')
                                                    ],
                                                    slug='num_immun_children'))
            agg_columns.insert(38, DatabaseColumn('Total no. of children from age >12 months',
                                                 AliasColumn('fully_immunized_eligible'),
                                                 slug='fully_immunized_eligible'))

            agg_columns.insert(40, DatabaseColumn('No. of children breastfed at birth',
                                                 AliasColumn('bf_at_birth'),
                                                 slug='bf_at_birth'))
            agg_columns.insert(41, DatabaseColumn('Total no. of children enrolled in ICDS-CAS system and born in last month',
                                                 AliasColumn('born_in_month'),
                                                 slug='born_in_month'))

            agg_columns.insert(43, DatabaseColumn('No. of children exclusively breastfed',
                                                 AliasColumn('ebf_in_month'),
                                                 slug='ebf_in_month'))
            agg_columns.insert(44, DatabaseColumn('Total number of children (0-6 months) of age enrolled in ICDS-CAS system',
                                                 AliasColumn('ebf_eligible'),
                                                 slug='ebf_eligible'))

            agg_columns.insert(46, DatabaseColumn('No. of children initiated complementary feeding (in the past 30 days)',
                                                 AliasColumn('cf_initiation_in_month'),
                                                 slug='cf_initiation_in_month'))
            agg_columns.insert(47, DatabaseColumn('Total no. of children (6-8 ) months of age enrolled with ICDS-CAS',
                                                 AliasColumn('cf_initiation_eligible'),
                                                 slug='cf_initiation_eligible'))

            agg_columns.insert(49, DatabaseColumn('No. of children initiated appropriate complementary feeding',
                                                 AliasColumn('cf_in_month'),
                                                 slug='cf_in_month'))
            agg_columns.insert(50, DatabaseColumn('No.of children (6-24) months of age enrolled with ICDS-CAS',
                                                 AliasColumn('cf_eligible'),
                                                 slug='cf_eligible'))

            agg_columns.insert(52, DatabaseColumn('No.of children receiving complementary feeding with adequate diet diversity',
                                                 AliasColumn('cf_diet_diversity'),
                                                 slug='cf_diet_diversity'))
            agg_columns.insert(53, DatabaseColumn('Total number of children (6 months - 2 yrs) of age enrolled with ICDS-CAS',
                                                 AliasColumn('cf_eligible'),
                                                 slug='cf_eligible'))

            agg_columns.insert(55, DatabaseColumn('No. of children initiated complementary feeding with adequate diet quantity',
                                                 AliasColumn('cf_diet_quantity'),
                                                 slug='cf_diet_quantity'))
            agg_columns.insert(56, DatabaseColumn('No.of children (6-24) months of age enrolled with ICDS-CAS',
                                                 AliasColumn('cf_eligible'),
                                                 slug='cf_eligible'))

            agg_columns.insert(58, DatabaseColumn('Total Number of children receiving complementary feeding '
                                                  'with appropriate handwashing before feeding',
                                                 AliasColumn('cf_handwashing'),
                                                 slug='cf_handwashing'))
            agg_columns.insert(59, DatabaseColumn('No.of children (6-24) months of age enrolled with ICDS-CAS',
                                                 AliasColumn('cf_eligible'),
                                                 slug='cf_eligible'))
        return columns + agg_columns
