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

            DatabaseColumn(
                'Total no. of children weighed',
                SumWhen(
                    whens={"age_tranche != :age_72": 'nutrition_status_weighed'}, else_=0,
                    alias='nutrition_status_weighed'
                ),
                slug='nutrition_status_weighed'
            ),
            DatabaseColumn(
                'Total no. of children eligible to be weighed',
                SumWhen(
                    whens={"age_tranche != :age_72": 'wer_eligible'}, else_=0,
                    alias='wer_eligible'
                ),
                slug='wer_eligible'
            ),
            AggregateColumn(
                'Weighing efficiency (in month)',
                percent,
                [
                    AliasColumn('nutrition_status_weighed'),
                    AliasColumn('wer_eligible'),
                ],
                slug='percent_weight_efficiency'
            ),
            DatabaseColumn(
                'Total no. of children whose height was measured',
                SumWhen(
                    whens={"age_tranche != :age_72": 'height_measured_in_month'}, else_=0,
                    alias='height_measured_in_month_efficiency'
                ),
                slug='height_measured_in_month_efficiency'
            ),
            DatabaseColumn(
                'Total no. of children  eligible for measuring height ',
                SumWhen(
                    whens={"age_tranche != :age_72": 'height_eligible'}, else_=0,
                    alias='height_eligible',
                ),
                slug='height_eligible'
            ),
            AggregateColumn(
                'Height measurement efficiency (in month)',
                percent,
                [
                    AliasColumn('height_measured_in_month_efficiency'),
                    AliasColumn('height_eligible')
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
            DatabaseColumn(
                'No. of severely underweight children',
                SumWhen(
                    whens={"age_tranche != :age_72": 'nutrition_status_severely_underweight'}, else_=0,
                    alias='nutrition_status_severely_underweight'
                ),
                slug='nutrition_status_severely_underweight'
            ),
            DatabaseColumn(
                'Total No. of children weighed',
                AliasColumn('nutrition_status_weighed'),
                slug='nutrition_status_weighed'
            ),
            AggregateColumn(
                'Percentage of severely underweight children',
                percent,
                [
                    AliasColumn('nutrition_status_severely_underweight'),
                    AliasColumn('nutrition_status_weighed'),
                ],
                slug='percent_severe_underweight'
            ),

            DatabaseColumn(
                'No. of moderately underweight children ',
                SumWhen(
                    whens={"age_tranche != :age_72": 'nutrition_status_moderately_underweight'}, else_=0,
                    alias='nutrition_status_moderately_underweight'
                ),
                slug='nutrition_status_moderately_underweight'
            ),
            DatabaseColumn(
                'Total No. of children weighed',
                AliasColumn('nutrition_status_weighed'),
                slug='nutrition_status_weighed'
            ),
            AggregateColumn(
                'Percentage of moderately underweight children',
                percent,
                [
                    AliasColumn('nutrition_status_moderately_underweight'),
                    AliasColumn('nutrition_status_weighed'),
                ],
                slug='percent_moderate_underweight'
            ),

            DatabaseColumn(
                'No. of  children with normal weight for age',
                SumWhen(
                    whens={"age_tranche != :age_72": 'nutrition_status_normal'}, else_=0,
                    alias='nutrition_status_normal'
                ),
                slug='nutrition_status_normal'
            ),
            DatabaseColumn(
                'Total No. of children weighed',
                AliasColumn('nutrition_status_weighed'),
                slug='nutrition_status_weighed'
            ),
            AggregateColumn(
                'Percentage of normal weight-for-age children',
                percent,
                [
                    AliasColumn('nutrition_status_normal'),
                    AliasColumn('nutrition_status_weighed'),
                ],
                slug='percent_normal_weight'
            ),
            DatabaseColumn(
                'No. of Children with severe wasting',
                SumWhen(
                    whens={get_age_condition(self.beta): wasting_severe_column(self.beta)},
                    alias='wasting_severe'
                ),
                slug='wasting_severe'
            ),
            DatabaseColumn(
                'Total number of children whose height and weight is measured ',
                SumWhen(
                    whens={get_age_condition(self.beta): wfh_recorded_in_month_column(self.beta)},
                    alias='weighed_and_height_measured_in_month'
                ),
                slug='weighed_and_height_measured_in_month'
            ),
            AggregateColumn(
                'Percentage of children with severe wasting',
                percent,
                [
                    AliasColumn('wasting_severe'),
                    AliasColumn('weighed_and_height_measured_in_month'),
                ],
                slug='percent_severe_wasting'
            ),

            DatabaseColumn(
                'No. of moderately wasted children',
                SumWhen(
                    whens={get_age_condition(self.beta): wasting_moderate_column(self.beta)},
                    alias='wasting_moderate'
                ),
                slug='wasting_moderate'
            ),
            DatabaseColumn(
                'Total number of children whose height and weight is measured ',
                AliasColumn('weighed_and_height_measured_in_month'),
                slug='weighed_and_height_measured_in_month'
            ),
            AggregateColumn(
                'Percentage of children with moderate wasting',
                percent,
                [
                    AliasColumn('wasting_moderate'),
                    AliasColumn('weighed_and_height_measured_in_month')
                ],
                slug='percent_moderate_wasting'
            ),

            DatabaseColumn(
                'No. of children with normal weight-for-height',
                SumWhen(
                    whens={get_age_condition(self.beta): wasting_normal_column(self.beta)},
                    alias='wasting_normal'
                ),
                slug='wasting_normal'
            ),
            DatabaseColumn(
                'Total no. of children  whose height and weight is measured ',
                AliasColumn('weighed_and_height_measured_in_month'),
                slug='weighed_and_height_measured_in_month'
            ),
            AggregateColumn(
                'Percentage of children with normal weight-for-height',
                percent,
                [
                    AliasColumn('wasting_normal'),
                    AliasColumn('weighed_and_height_measured_in_month')
                ],
                slug='percent_normal_wasting'
            ),

            DatabaseColumn(
                'No. of severely stunted children',
                SumWhen(
                    whens={get_age_condition(self.beta): stunting_severe_column(self.beta)},
                    alias='stunting_severe'
                ),
                slug='stunting_severe'
            ),
            DatabaseColumn(
                'Total no. of children whose height has been measured ',
                SumWhen(
                    whens={get_age_condition(self.beta): hfa_recorded_in_month_column(self.beta)},
                    alias='height_measured_in_month'
                ),
                slug='height_measured_in_month'
            ),
            AggregateColumn(
                'Percentage of children with severe stunting',
                percent,
                [
                    AliasColumn('stunting_severe'),
                    AliasColumn('height_measured_in_month'),
                ],
                slug='percent_severe_stunting'
            ),

            DatabaseColumn(
                'No. of moderately stunted children',
                SumWhen(
                    whens={get_age_condition(self.beta): stunting_moderate_column(self.beta)},
                    alias='stunting_moderate'
                ),
                slug='stunting_moderate'
            ),
            DatabaseColumn(
                'Total no. of children whose height has been measured ',
                AliasColumn('height_measured_in_month'),
                slug='height_measured_in_month'
            ),
            AggregateColumn(
                'Percentage of children with moderate stunting',
                percent,
                [
                    AliasColumn('stunting_moderate'),
                    AliasColumn('height_measured_in_month')
                ],
                slug='percent_moderate_stunting'
            ),

            DatabaseColumn(
                'No. of children with normal height for age',
                SumWhen(
                    whens={get_age_condition(self.beta): stunting_normal_column(self.beta)},
                    alias='stunting_normal'
                ),
                slug='stunting_normal'
            ),
            DatabaseColumn(
                'Total no. of children whose height has been measured ',
                AliasColumn('height_measured_in_month'),
                slug='height_measured_in_month'
            ),
            AggregateColumn(
                'Percentage of children with normal height-for-age',
                percent,
                [
                    AliasColumn('stunting_normal'),
                    AliasColumn('height_measured_in_month')
                ],
                slug='percent_normal_stunting'
            ),

            DatabaseColumn(
                'No. of newborns with low birth weight',
                SumColumn('low_birth_weight_in_month',
                          alias='low_birth_weight_in_month')
            ),
            DatabaseColumn(
                'Total no. of children born and weighed in the current month',
                SumColumn('weighed_and_born_in_month',
                          alias='weighed_and_born_in_month')
            ),
            AggregateColumn(
                'Percent of newborns with low birth weight',
                percent,
                [
                    AliasColumn('low_birth_weight_in_month'),
                    AliasColumn('weighed_and_born_in_month')
                ],
                slug='newborn_low_birth_weight'
            ),

            AggregateColumn(
                'No. of children completed 1 year immunization ',
                lambda x, y: ((x or 0) + (y or 0)),
                [
                    SumColumn('fully_immunized_on_time',
                              alias='fully_immunized_on_time'),
                    SumColumn('fully_immunized_late',
                              alias='fully_immunized_late'),
                ]
            ),
            DatabaseColumn(
                'Total no. of children from age >12 months',
                SumColumn('fully_immunized_eligible',
                          alias='fully_immunized_eligible')
            ),
            AggregateColumn(
                'Percentage of children with completed 1 year immunizations',
                lambda x, y, z: '%.2f%%' % (((x or 0) + (y or 0)) * 100 / float(z or 1)),
                [
                    AliasColumn('fully_immunized_on_time'),
                    AliasColumn('fully_immunized_late'),
                    AliasColumn('fully_immunized_eligible')
                ],
                slug='percent_completed_1year_immunizations'
            ),

            DatabaseColumn(
                'No. of children breastfed at birth',
                SumColumn('bf_at_birth',
                          alias='bf_at_birth')
            ),
            DatabaseColumn(
                'Total no. of children enrolled in ICDS-CAS system and born in last month',
                SumColumn('born_in_month',
                          alias='born_in_month')
            ),
            AggregateColumn(
                'Percentage of children breastfed at birth',
                percent,
                [
                    AliasColumn('bf_at_birth'),
                    AliasColumn('born_in_month')
                ],
                slug='percent_breastfed_at_birth'
            ),

            DatabaseColumn(
                'No. of children exclusively breastfed',
                SumColumn('ebf_in_month',
                          alias='ebf_in_month')
            ),
            DatabaseColumn(
                'Total number of children (0-6 months) of age enrolled in ICDS-CAS system ',
                SumColumn('ebf_eligible',
                          alias='ebf_eligible')
            ),
            AggregateColumn(
                'Percentage of children exclusively breastfeeding',
                percent,
                [
                    AliasColumn('ebf_in_month'),
                    AliasColumn('ebf_eligible')
                ],
                slug='percent_ebf'
            ),

            DatabaseColumn(
                'No. of children initiated complementary feeding (in the past 30 days)',
                SumColumn('cf_initiation_in_month',
                          alias='cf_initiation_in_month')
            ),
            DatabaseColumn(
                'Total no. of children (6-8 ) months of age enrolled with ICDS-CAS',
                SumColumn('cf_initiation_eligible',
                          alias='cf_initiation_eligible')
            ),
            AggregateColumn(
                'Percentage of children initiated complementary feeding (in the past 30 days)',
                percent,
                [
                    AliasColumn('cf_initiation_in_month'),
                    AliasColumn('cf_initiation_eligible')
                ],
                slug='percent_initiated_on_cf'
            ),

            DatabaseColumn(
                'No. of children initiated appropriate complementary feeding',
                SumColumn('cf_in_month',
                          alias='cf_in_month')
            ),
            DatabaseColumn(
                'No.of children (6-24) months of age enrolled with ICDS-CAS',
                SumColumn('cf_eligible',
                          alias='cf_eligible')
            ),
            AggregateColumn(
                'Percentage of children initiated appropriate complementary feeding',
                percent,
                [
                    AliasColumn('cf_in_month'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_appropriate_cf'
            ),

            DatabaseColumn(
                'No.of children receiving complementary feeding with adequate diet diversity',
                SumColumn('cf_diet_diversity',
                          alias='cf_diet_diversity')
            ),
            DatabaseColumn(
                'Total number of children (6 months - 2 yrs) of age enrolled with ICDS-CAS',
                AliasColumn('cf_eligible')
            ),
            AggregateColumn(
                'Percentage of children receiving complementary feeding with adequate diet diversity',
                percent,
                [
                    AliasColumn('cf_diet_diversity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_diversity'
            ),


            DatabaseColumn(
                'No. of children initiated complementary feeding with adequate diet quanity',
                SumColumn('cf_diet_quantity',
                          alias='cf_diet_quantity')
            ),
            DatabaseColumn(
                'No.of children (6-24) months of age enrolled with ICDS-CAS',
                AliasColumn('cf_eligible')
            ),
            AggregateColumn(
                'Percentage of children receiving complementary feeding with adequate diet quanity',
                percent,
                [
                    AliasColumn('cf_diet_quantity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_quanity'
            ),


            DatabaseColumn(
                'Total Number of children receiving complementary feeding with appropriate handwashing before feeding',
                SumColumn('cf_handwashing',
                          alias='cf_handwashing')
            ),
            DatabaseColumn(
                'No.of children (6-24) months of age enrolled with ICDS-CAS',
                AliasColumn('cf_eligible')
            ),
            AggregateColumn(
                "Percentage of children receiving complementary feeding "
                "with appropriate handwashing before feeding",
                percent,
                [
                    AliasColumn('cf_handwashing'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_handwashing_before_feeding'
            ),
        ]
        return columns + agg_columns
