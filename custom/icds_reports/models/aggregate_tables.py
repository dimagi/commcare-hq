from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta
from django.db import connections, models

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.routers import db_for_read_write
from custom.icds_reports.const import (
    AGG_COMP_FEEDING_TABLE,
    AGG_CCS_RECORD_PNC_TABLE,
    AGG_CHILD_HEALTH_PNC_TABLE,
    AGG_CHILD_HEALTH_THR_TABLE,
    AGG_GROWTH_MONITORING_TABLE,
)
from custom.icds_reports.utils.aggregation import (
    ComplementaryFormsAggregationHelper,
    GrowthMonitoringFormsAggregationHelper,
    PostnatalCareFormsChildHealthAggregationHelper,
    PostnatalCareFormsCcsRecordAggregationHelper,
    THRFormsChildHealthAggregationHelper,
)


class CcsRecordMonthly(models.Model):
    awc_id = models.TextField()
    case_id = models.TextField(primary_key=True)
    month = models.DateField()
    age_in_months = models.IntegerField(blank=True, null=True)
    ccs_status = models.TextField(blank=True, null=True)
    open_in_month = models.IntegerField(blank=True, null=True)
    alive_in_month = models.IntegerField(blank=True, null=True)
    trimester = models.IntegerField(blank=True, null=True)
    num_rations_distributed = models.IntegerField(blank=True, null=True)
    thr_eligible = models.IntegerField(blank=True, null=True)
    tetanus_complete = models.IntegerField(blank=True, null=True)
    delivered_in_month = models.IntegerField(blank=True, null=True)
    anc1_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc2_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc3_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc4_received_at_delivery = models.IntegerField(blank=True, null=True)
    registration_trimester_at_delivery = models.IntegerField(blank=True, null=True)
    using_ifa = models.IntegerField(blank=True, null=True)
    ifa_consumed_last_seven_days = models.IntegerField(blank=True, null=True)
    anemic_severe = models.IntegerField(blank=True, null=True)
    anemic_moderate = models.IntegerField(blank=True, null=True)
    anemic_normal = models.IntegerField(blank=True, null=True)
    anemic_unknown = models.IntegerField(blank=True, null=True)
    extra_meal = models.IntegerField(blank=True, null=True)
    resting_during_pregnancy = models.IntegerField(blank=True, null=True)
    bp_visited_in_month = models.IntegerField(blank=True, null=True)
    pnc_visited_in_month = models.IntegerField(blank=True, null=True)
    trimester_2 = models.IntegerField(blank=True, null=True)
    trimester_3 = models.IntegerField(blank=True, null=True)
    counsel_immediate_bf = models.IntegerField(blank=True, null=True)
    counsel_bp_vid = models.IntegerField(blank=True, null=True)
    counsel_preparation = models.IntegerField(blank=True, null=True)
    counsel_fp_vid = models.IntegerField(blank=True, null=True)
    counsel_immediate_conception = models.IntegerField(blank=True, null=True)
    counsel_accessible_postpartum_fp = models.IntegerField(blank=True, null=True)
    bp1_complete = models.IntegerField(blank=True, null=True)
    bp2_complete = models.IntegerField(blank=True, null=True)
    bp3_complete = models.IntegerField(blank=True, null=True)
    pnc_complete = models.IntegerField(blank=True, null=True)
    postnatal = models.IntegerField(blank=True, null=True)
    has_aadhar_id = models.IntegerField(blank=True, null=True)
    counsel_fp_methods = models.IntegerField(blank=True, null=True)
    pregnant = models.IntegerField(blank=True, null=True)
    pregnant_all = models.IntegerField(blank=True, null=True)
    lactating = models.IntegerField(blank=True, null=True)
    lactating_all = models.IntegerField(blank=True, null=True)
    institutional_delivery_in_month = models.IntegerField(blank=True, null=True)
    add = models.DateField(blank=True, null=True)
    anc_in_month = models.SmallIntegerField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'ccs_record_monthly'


class AwcLocation(models.Model):
    doc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField()
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField()
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField()
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField()
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    aww_name = models.TextField(blank=True, null=True)
    contact_phone_number = models.TextField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'awc_location'
        unique_together = (('state_id', 'district_id', 'block_id', 'supervisor_id', 'doc_id'),)


class ChildHealthMonthly(models.Model):
    awc_id = models.TextField()
    case_id = models.TextField(primary_key=True)
    month = models.DateField()
    age_in_months = models.IntegerField(blank=True, null=True)
    open_in_month = models.IntegerField(blank=True, null=True)
    alive_in_month = models.IntegerField(blank=True, null=True)
    wer_eligible = models.IntegerField(blank=True, null=True)
    nutrition_status_last_recorded = models.TextField(blank=True, null=True)
    current_month_nutrition_status = models.TextField(blank=True, null=True)
    nutrition_status_weighed = models.IntegerField(blank=True, null=True)
    num_rations_distributed = models.IntegerField(blank=True, null=True)
    pse_eligible = models.IntegerField(blank=True, null=True)
    pse_days_attended = models.IntegerField(blank=True, null=True)
    born_in_month = models.IntegerField(blank=True, null=True)
    low_birth_weight_born_in_month = models.IntegerField(blank=True, null=True)
    bf_at_birth_born_in_month = models.IntegerField(blank=True, null=True)
    ebf_eligible = models.IntegerField(blank=True, null=True)
    ebf_in_month = models.IntegerField(blank=True, null=True)
    ebf_not_breastfeeding_reason = models.TextField(blank=True, null=True)
    ebf_drinking_liquid = models.IntegerField(blank=True, null=True)
    ebf_eating = models.IntegerField(blank=True, null=True)
    ebf_no_bf_no_milk = models.IntegerField(blank=True, null=True)
    ebf_no_bf_pregnant_again = models.IntegerField(blank=True, null=True)
    ebf_no_bf_child_too_old = models.IntegerField(blank=True, null=True)
    ebf_no_bf_mother_sick = models.IntegerField(blank=True, null=True)
    cf_eligible = models.IntegerField(blank=True, null=True)
    cf_in_month = models.IntegerField(blank=True, null=True)
    cf_diet_diversity = models.IntegerField(blank=True, null=True)
    cf_diet_quantity = models.IntegerField(blank=True, null=True)
    cf_handwashing = models.IntegerField(blank=True, null=True)
    cf_demo = models.IntegerField(blank=True, null=True)
    fully_immunized_eligible = models.IntegerField(blank=True, null=True)
    fully_immunized_on_time = models.IntegerField(blank=True, null=True)
    fully_immunized_late = models.IntegerField(blank=True, null=True)
    counsel_ebf = models.IntegerField(blank=True, null=True)
    counsel_adequate_bf = models.IntegerField(blank=True, null=True)
    counsel_pediatric_ifa = models.IntegerField(blank=True, null=True)
    counsel_comp_feeding_vid = models.IntegerField(blank=True, null=True)
    counsel_increase_food_bf = models.IntegerField(blank=True, null=True)
    counsel_manage_breast_problems = models.IntegerField(blank=True, null=True)
    counsel_skin_to_skin = models.IntegerField(blank=True, null=True)
    counsel_immediate_breastfeeding = models.IntegerField(blank=True, null=True)
    recorded_weight = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    recorded_height = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    has_aadhar_id = models.IntegerField(blank=True, null=True)
    thr_eligible = models.IntegerField(blank=True, null=True)
    pnc_eligible = models.IntegerField(blank=True, null=True)
    cf_initiation_in_month = models.IntegerField(blank=True, null=True)
    cf_initiation_eligible = models.IntegerField(blank=True, null=True)
    height_measured_in_month = models.IntegerField(blank=True, null=True)
    current_month_stunting = models.TextField(blank=True, null=True)
    stunting_last_recorded = models.TextField(blank=True, null=True)
    wasting_last_recorded = models.TextField(blank=True, null=True)
    current_month_wasting = models.TextField(blank=True, null=True)
    valid_in_month = models.IntegerField(blank=True, null=True)
    valid_all_registered_in_month = models.IntegerField(blank=True, null=True)
    ebf_no_info_recorded = models.IntegerField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    sex = models.TextField(blank=True, null=True)
    age_tranche = models.TextField(blank=True, null=True)
    caste = models.TextField(blank=True, null=True)
    disabled = models.TextField(blank=True, null=True)
    minority = models.TextField(blank=True, null=True)
    resident = models.TextField(blank=True, null=True)
    person_name = models.TextField(blank=True, null=True)
    current_month_nutrition_status_sort = models.IntegerField(blank=True, null=True)
    current_month_stunting_sort = models.IntegerField(blank=True, null=True)
    current_month_wasting_sort = models.IntegerField(blank=True, null=True)
    mother_name = models.TextField(blank=True, null=True)
    fully_immunized = models.IntegerField(blank=True, null=True)
    immunization_in_month = models.SmallIntegerField(blank=True, null=True)
    days_ration_given_child = models.SmallIntegerField(blank=True, null=True)
    zscore_grading_hfa = models.SmallIntegerField(blank=True, null=True)
    zscore_grading_hfa_recorded_in_month = models.SmallIntegerField(blank=True, null=True)
    zscore_grading_wfh = models.SmallIntegerField(blank=True, null=True)
    zscore_grading_wfh_recorded_in_month = models.SmallIntegerField(blank=True, null=True)
    muac_grading = models.SmallIntegerField(blank=True, null=True)
    muac_grading_recorded_in_month = models.SmallIntegerField(blank=True, null=True)

    class Meta:
        app_label = 'icds_model'
        managed = False
        db_table = 'child_health_monthly'


def get_cursor(model):
    db = db_for_read_write(model)
    return connections[db].cursor()


class AggregateComplementaryFeedingForms(models.Model):
    """Aggregated data based on AWW App, Home Visit Scheduler module,
    Complementary Feeding form.

    A child table exists for each state_id and month.

    A row exists for every case that has ever had a Complementary Feeding Form
    submitted against it.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # primary key as it's unique for every partition
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )

    # Most of these could possibly be represented by a boolean, but have
    # historically been stored as integers because they are in SUM statements
    comp_feeding_ever = models.PositiveSmallIntegerField(
        null=True,
        help_text="Complementary feeding has ever occurred for this case"
    )
    demo_comp_feeding = models.PositiveSmallIntegerField(
        null=True,
        help_text="Demo of complementary feeding has ever occurred"
    )
    counselled_pediatric_ifa = models.PositiveSmallIntegerField(
        null=True,
        help_text="Once the child is over 1 year, has ever been counseled on pediatric IFA"
    )
    play_comp_feeding_vid = models.PositiveSmallIntegerField(
        null=True,
        help_text="Case has ever been counseled about complementary feeding with a video"
    )
    comp_feeding_latest = models.PositiveSmallIntegerField(
        null=True,
        help_text="Complementary feeding occurred for this case in the latest form"
    )
    diet_diversity = models.PositiveSmallIntegerField(
        null=True,
        help_text="Diet diversity occurred for this case in the latest form"
    )
    diet_quantity = models.PositiveSmallIntegerField(
        null=True,
        help_text="Diet quantity occurred for this case in the latest form"
    )
    hand_wash = models.PositiveSmallIntegerField(
        null=True,
        help_text="Hand washing occurred for this case in the latest form"
    )

    class Meta(object):
        db_table = AGG_COMP_FEEDING_TABLE

    @classmethod
    def aggregate(cls, state_id, month):
        helper = ComplementaryFormsAggregationHelper(state_id, month)
        prev_month_query, prev_month_params = helper.create_table_query(month - relativedelta(months=1))
        curr_month_query, curr_month_params = helper.create_table_query()
        agg_query, agg_params = helper.aggregation_query()

        with get_cursor(cls) as cursor:
            cursor.execute(prev_month_query, prev_month_params)
            cursor.execute(helper.drop_table_query())
            cursor.execute(curr_month_query, curr_month_params)
            cursor.execute(agg_query, agg_params)

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        helper = ComplementaryFormsAggregationHelper(state_id, month)
        query, params = helper.compare_with_old_data_query()

        with get_cursor(AggregateComplementaryFeedingForms) as cursor:
            cursor.execute(query, params)
            rows = fetchall_as_namedtuple(cursor)
            return [row.child_health_case_id for row in rows]


class AggregateChildHealthPostnatalCareForms(models.Model):
    """Aggregated data for child health cases based on
    AWW App, Home Visit Scheduler module,
    Post Natal Care and Exclusive Breastfeeding forms.

    A child table exists for each state_id and month.

    A row exists for every case that has ever had a Complementary Feeding Form
    submitted against it.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # primary key as it's unique for every partition
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )
    counsel_increase_food_bf = models.PositiveSmallIntegerField(
        null=True,
        help_text="Counseling on increasing food intake has ever been completed"
    )
    counsel_breast = models.PositiveSmallIntegerField(
        null=True,
        help_text="Counseling on managing breast problems has ever been completed"
    )
    skin_to_skin = models.PositiveSmallIntegerField(
        null=True,
        help_text="Counseling on skin to skin care has ever been completed"
    )
    is_ebf = models.PositiveSmallIntegerField(
        null=True,
        help_text="is_ebf set in the last form submitted this month"
    )
    water_or_milk = models.PositiveSmallIntegerField(
        null=True,
        help_text="Child given water or milk in the last form submitted this month"
    )
    other_milk_to_child = models.PositiveSmallIntegerField(
        null=True,
        help_text="Child given something other than milk in the last form submitted this month"
    )
    tea_other = models.PositiveSmallIntegerField(
        null=True,
        help_text="Child given tea or other liquid in the last form submitted this month"
    )
    eating = models.PositiveSmallIntegerField(
        null=True,
        help_text="Child given something to eat in the last form submitted this month"
    )
    counsel_exclusive_bf = models.PositiveSmallIntegerField(
        null=True,
        help_text="Counseling about exclusive breastfeeding has ever occurred"
    )
    counsel_only_milk = models.PositiveSmallIntegerField(
        null=True,
        help_text="Counseling about avoiding other than breast milk has ever occurred"
    )
    counsel_adequate_bf = models.PositiveSmallIntegerField(
        null=True,
        help_text="Counseling about adequate breastfeeding has ever occurred"
    )
    not_breastfeeding = models.CharField(
        null=True,
        max_length=126,
        help_text="The reason the mother is not able to breastfeed"
    )

    class Meta(object):
        db_table = AGG_CHILD_HEALTH_PNC_TABLE

    @classmethod
    def aggregate(cls, state_id, month):
        helper = PostnatalCareFormsChildHealthAggregationHelper(state_id, month)
        prev_month_query, prev_month_params = helper.create_table_query(month - relativedelta(months=1))
        curr_month_query, curr_month_params = helper.create_table_query()
        agg_query, agg_params = helper.aggregation_query()

        with get_cursor(cls) as cursor:
            cursor.execute(prev_month_query, prev_month_params)
            cursor.execute(helper.drop_table_query())
            cursor.execute(curr_month_query, curr_month_params)
            cursor.execute(agg_query, agg_params)

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        helper = PostnatalCareFormsChildHealthAggregationHelper(state_id, month)
        query, params = helper.compare_with_old_data_query()

        with get_cursor(AggregateComplementaryFeedingForms) as cursor:
            cursor.execute(query, params)
            rows = fetchall_as_namedtuple(cursor)
            return [row.child_health_case_id for row in rows]


class AggregateCcsRecordPostnatalCareForms(models.Model):
    """Aggregated data for ccs record cases based on
    AWW App, Home Visit Scheduler module,
    Post Natal Care and Exclusive Breastfeeding forms.

    A child table exists for each state_id and month.

    A row exists for every case that has ever had a Complementary Feeding Form
    submitted against it.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # primary key as it's unique for every partition
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )
    counsel_methods = models.PositiveSmallIntegerField(
        null=True,
        help_text="Counseling about family planning methods has ever occurred"
    )

    class Meta(object):
        db_table = AGG_CCS_RECORD_PNC_TABLE

    @classmethod
    def aggregate(cls, state_id, month):
        helper = PostnatalCareFormsCcsRecordAggregationHelper(state_id, month)
        prev_month_query, prev_month_params = helper.create_table_query(month - relativedelta(months=1))
        curr_month_query, curr_month_params = helper.create_table_query()
        agg_query, agg_params = helper.aggregation_query()

        with get_cursor(cls) as cursor:
            cursor.execute(prev_month_query, prev_month_params)
            cursor.execute(helper.drop_table_query())
            cursor.execute(curr_month_query, curr_month_params)
            cursor.execute(agg_query, agg_params)

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        helper = PostnatalCareFormsCcsRecordAggregationHelper(state_id, month)
        query, params = helper.compare_with_old_data_query()

        with get_cursor(AggregateComplementaryFeedingForms) as cursor:
            cursor.execute(query, params)
            rows = fetchall_as_namedtuple(cursor)
            return [row.child_health_case_id for row in rows]


class AggregateChildHealthTHRForms(models.Model):
    """Aggregated data for child_health cases based on
    Take Home Ration forms

    A child table exists for each state_id and month.

    A row exists for every child_health case that has had a THR Form
    submitted against it this month.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # primary key as it's unique for every partition
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )
    days_ration_given_child = models.PositiveSmallIntegerField(
        null=True,
        help_text="Number of days the child has been given rations this month"
    )

    class Meta(object):
        db_table = AGG_CHILD_HEALTH_THR_TABLE

    @classmethod
    def aggregate(cls, state_id, month):
        helper = THRFormsChildHealthAggregationHelper(state_id, month)
        curr_month_query, curr_month_params = helper.create_table_query()
        agg_query, agg_params = helper.aggregation_query()

        with get_cursor(cls) as cursor:
            cursor.execute(helper.drop_table_query())
            cursor.execute(curr_month_query, curr_month_params)
            cursor.execute(agg_query, agg_params)


class AggregateGrowthMonitoringForms(models.Model):
    """Aggregated data based on AWW App

    376FA2E1 -> Delivery
    b183124a -> Growth Monitoring
    7a557541 -> Advanced Growth Monitoring

    A child table exists for each state_id and month.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # primary key as it's unique for every partition
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )

    weight_child = models.DecimalField(
        max_digits=64, decimal_places=16, null=True,
        help_text="Last recorded weight_child case property"
    )
    weight_child_last_recorded = models.DateTimeField(
        null=True, help_text="Time when weight_child was last recorded"
    )
    height_child = models.DecimalField(
        max_digits=64, decimal_places=16, null=True,
        help_text="Last recorded height_child case property"
    )
    height_child_last_recorded = models.DateTimeField(
        null=True, help_text="Time when height_child was last recorded"
    )

    zscore_grading_wfa = models.PositiveSmallIntegerField(
        null=True, help_text="Last recorded zscore_grading_wfa before end of this month"
    )
    zscore_grading_wfa_last_recorded = models.DateTimeField(
        null=True, help_text="Time when zscore_grading_wfa was last recorded"
    )

    zscore_grading_hfa = models.PositiveSmallIntegerField(
        null=True, help_text="Last recorded zscore_grading_hfa before end of this month"
    )
    zscore_grading_hfa_last_recorded = models.DateTimeField(
        null=True, help_text="Time when zscore_grading_hfa was last recorded"
    )

    zscore_grading_wfh = models.PositiveSmallIntegerField(
        null=True, help_text="Last recorded zscore_grading_wfh before end of this month"
    )
    zscore_grading_wfh_last_recorded = models.DateTimeField(
        null=True, help_text="Time when zscore_grading_wfh was last recorded"
    )

    muac_grading = models.PositiveSmallIntegerField(
        null=True, help_text="Last recorded muac_grading before end of this month"
    )
    muac_grading_last_recorded = models.DateTimeField(
        null=True, help_text="Time when muac_grading was last recorded"
    )

    class Meta(object):
        db_table = AGG_GROWTH_MONITORING_TABLE

    @classmethod
    def aggregate(cls, state_id, month):
        helper = GrowthMonitoringFormsAggregationHelper(state_id, month)
        prev_month_query, prev_month_params = helper.create_table_query(month - relativedelta(months=1))
        curr_month_query, curr_month_params = helper.create_table_query()
        aggregate_queries = helper.aggregation_queries()

        with get_cursor(cls) as cursor:
            cursor.execute(prev_month_query, prev_month_params)
            cursor.execute(helper.drop_table_query())
            cursor.execute(curr_month_query, curr_month_params)
            for query, params in aggregate_queries:
                cursor.execute(query, params)

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        helper = GrowthMonitoringFormsAggregationHelper(state_id, month)
        query, params = helper.compare_with_old_data_query()

        with get_cursor(cls) as cursor:
            cursor.execute(query, params)
            rows = fetchall_as_namedtuple(cursor)
            return [row.child_health_case_id for row in rows]
