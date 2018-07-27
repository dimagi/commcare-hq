from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import models


class AggAwcDailyView(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    cases_household = models.IntegerField(blank=True, null=True)
    cases_person = models.IntegerField(blank=True, null=True)
    cases_person_all = models.IntegerField(blank=True, null=True)
    cases_person_has_aadhaar = models.IntegerField(blank=True, null=True)
    cases_person_beneficiary = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_11_14 = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_15_18 = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_11_14_all = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_15_18_all = models.IntegerField(blank=True, null=True)
    cases_ccs_pregnant = models.IntegerField(blank=True, null=True)
    cases_ccs_lactating = models.IntegerField(blank=True, null=True)
    cases_child_health = models.IntegerField(blank=True, null=True)
    cases_ccs_pregnant_all = models.IntegerField(blank=True, null=True)
    cases_ccs_lactating_all = models.IntegerField(blank=True, null=True)
    cases_child_health_all = models.IntegerField(blank=True, null=True)
    daily_attendance_open = models.IntegerField(blank=True, null=True)
    num_awcs = models.IntegerField(blank=True, null=True)
    num_launched_states = models.IntegerField(blank=True, null=True)
    num_launched_districts = models.IntegerField(blank=True, null=True)
    num_launched_blocks = models.IntegerField(blank=True, null=True)
    num_launched_supervisors = models.IntegerField(blank=True, null=True)
    num_launched_awcs = models.IntegerField(blank=True, null=True)
    cases_person_has_aadhaar_v2 = models.IntegerField(blank=True, null=True)
    cases_person_beneficiary_v2 = models.IntegerField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'agg_awc_daily_view'


class DailyAttendanceView(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    doc_id = models.TextField(blank=True, null=True)
    pse_date = models.DateField(blank=True, null=True)
    awc_open_count = models.IntegerField(blank=True, null=True)
    count = models.IntegerField(blank=True, null=True)
    eligible_children = models.IntegerField(blank=True, null=True)
    attended_children = models.IntegerField(blank=True, null=True)
    attended_children_percent = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    form_location = models.TextField(blank=True, null=True)
    form_location_lat = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    form_location_long = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    image_name = models.TextField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'daily_attendance_view'


class ChildHealthMonthlyView(models.Model):
    """Contains one row for the status of every child_health case at the end of each month
    """
    case_id = models.TextField(primary_key=True)
    awc_id = models.TextField(blank=True, null=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    person_name = models.TextField(blank=True, null=True)
    mother_name = models.TextField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    sex = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    age_in_months = models.IntegerField(
        blank=True, null=True, help_text="age in months at the end of the month"
    )
    open_in_month = models.IntegerField(
        blank=True, null=True, help_text="Open at the end of the month"
    )
    valid_in_month = models.IntegerField(
        blank=True, null=True,
        help_text="Open, alive, registered_status != 'not_registered', "
        "migration_status != 'migrated', age at start of month < 73 months"
    )
    nutrition_status_last_recorded = models.TextField(
        blank=True, null=True,
        help_text="based on zscore_grading_wfa, "
        "Either 'severely_underweight', 'moderately_underweight', or 'normal' "
        "when age at start of month < 61 months and valid_in_month "
        "or NULL otherwise"
    )
    current_month_nutrition_status = models.TextField(
        blank=True, null=True,
        help_text="nutrition_status_last_recorded if recorded in the month"
    )
    pse_days_attended = models.IntegerField(
        blank=True, null=True,
        help_text="Number of days a Daily Feeing Form has been submitted against this child case"
        "when valid_in_month and age in months between 36 and 72 months"
    )
    recorded_weight = models.DecimalField(
        max_digits=65535, decimal_places=65535, blank=True, null=True,
        help_text="weight_child if it has been recorded in the month"
    )
    recorded_height = models.DecimalField(
        max_digits=65535, decimal_places=65535, blank=True, null=True,
        help_text="height_child if it has been recorded in the month"
    )
    thr_eligible = models.IntegerField(
        blank=True, null=True,
        help_text="valid_in_month and age between 6 and 36 months"
    )
    current_month_stunting = models.TextField(
        blank=True, null=True,
        help_text="based on zscore_grading_hfa, "
        "Either 'severe', 'moderate', or 'normal' "
        "when valid_in_monthand zscore_grading_hfa changed in month"
        "or 'unmeasured' otherwise"
    )
    current_month_wasting = models.TextField(
        blank=True, null=True,
        help_text="based on zscore_grading_wfh, "
        "Either 'severe', 'moderate', or 'normal' "
        "when valid_in_monthand zscore_grading_wfh changed in month"
        "or 'unmeasured' otherwise"
    )
    fully_immunized = models.IntegerField(
        blank=True, null=True, help_text="Child has been immunized"
    )
    current_month_nutrition_status_sort = models.IntegerField(blank=True, null=True)
    current_month_stunting_sort = models.IntegerField(blank=True, null=True)
    current_month_wasting_sort = models.IntegerField(blank=True, null=True)
    current_month_stunting_v2 = models.TextField(blank=True, null=True)
    current_month_wasting_v2 = models.TextField(blank=True, null=True)
    current_month_stunting_v2_sort = models.IntegerField(blank=True, null=True)
    current_month_wasting_v2_sort = models.IntegerField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'child_health_monthly_view'


class AggAwcMonthly(models.Model):
    """Contains one row for the status of every AWC, Supervisor, Block,
    District and State at the end of each month

    For rows for higher level of locations, the lower levels are 'All'.
    For example, in a supervisor row, awc_id = 'All'
    """
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(
        blank=True, null=True, help_text="1 for state rows, 2 for district rows, and so on"
    )
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    aww_name = models.TextField(blank=True, null=True)
    contact_phone_number = models.TextField(blank=True, null=True)
    num_awcs = models.IntegerField(blank=True, null=True, help_text="number of AWCs")
    num_launched_states = models.IntegerField(blank=True, null=True)
    num_launched_districts = models.IntegerField(blank=True, null=True)
    num_launched_blocks = models.IntegerField(blank=True, null=True)
    num_launched_supervisors = models.IntegerField(blank=True, null=True)
    num_launched_awcs = models.IntegerField(
        blank=True, null=True,
        help_text="number of AWCs that have at least one Household registration form"
    )
    awc_days_open = models.IntegerField(
        blank=True, null=True,
        help_text="Days an AWC has submitted an Daily Feeding Form in this month"
    )
    awc_days_pse_conducted = models.IntegerField(
        blank=True, null=True, help_text="Days an AWC has conducted pse in this month"
    )
    awc_num_open = models.IntegerField(
        blank=True, null=True, help_text="Number of AWC where awc_days_open > 1 for this month"
    )
    wer_weighed = models.IntegerField(
        blank=True, null=True, help_text="Number of children that have been weighed in the month"
    )
    wer_eligible = models.IntegerField(
        blank=True, null=True, help_text="Number of children valid_in_month and age < 60 months"
    )
    num_anc_visits = models.IntegerField(
        blank=True, null=True, help_text="Number of anc_visits in the month"
    )
    num_children_immunized = models.IntegerField(
        blank=True, null=True, help_text="Number of children immunized in the month"
    )
    cases_household = models.IntegerField(
        blank=True, null=True, help_text="Number of open household cases"
    )
    cases_person = models.IntegerField(
        blank=True, null=True,
        help_text="Number of open person cases where registered_status != 'not_registered' and "
        "migration_status != 'migrated'"
    )
    cases_person_all = models.IntegerField(
        blank=True, null=True, help_text="Number of open person cases"
    )
    cases_person_has_aadhaar = models.IntegerField(blank=True, null=True, help_text="no longer used")
    cases_person_beneficiary = models.IntegerField(blank=True, null=True, help_text="no longer used")
    cases_person_adolescent_girls_11_14 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of cases_person that are female between 11 and 14 years"
    )
    cases_person_adolescent_girls_15_18 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of cases_person that are female between 15 and 18 years"
    )
    cases_person_adolescent_girls_11_14_all = models.IntegerField(
        blank=True, null=True,
        help_text="Number of cases_person_all that are female between 11 and 14 years"
    )
    cases_person_adolescent_girls_15_18_all = models.IntegerField(
        blank=True, null=True,
        help_text="Number of cases_person_all that are female between 15 and 18 years"
    )
    cases_person_referred = models.IntegerField(
        blank=True, null=True,
        help_text="Number of person cases whose last_referral_date is in this month"
    )
    cases_ccs_pregnant = models.IntegerField(blank=True, null=True)
    cases_ccs_lactating = models.IntegerField(blank=True, null=True)
    cases_child_health = models.IntegerField(blank=True, null=True)
    cases_ccs_pregnant_all = models.IntegerField(blank=True, null=True)
    cases_ccs_lactating_all = models.IntegerField(blank=True, null=True)
    cases_child_health_all = models.IntegerField(blank=True, null=True)
    usage_num_pse = models.IntegerField(blank=True, null=True)
    usage_num_gmp = models.IntegerField(blank=True, null=True)
    usage_num_thr = models.IntegerField(blank=True, null=True)
    usage_num_home_visit = models.IntegerField(blank=True, null=True)
    usage_num_bp_tri1 = models.IntegerField(blank=True, null=True)
    usage_num_bp_tri2 = models.IntegerField(blank=True, null=True)
    usage_num_bp_tri3 = models.IntegerField(blank=True, null=True)
    usage_num_pnc = models.IntegerField(blank=True, null=True)
    usage_num_ebf = models.IntegerField(blank=True, null=True)
    usage_num_cf = models.IntegerField(blank=True, null=True)
    usage_num_delivery = models.IntegerField(blank=True, null=True)
    usage_num_due_list_ccs = models.IntegerField(blank=True, null=True)
    usage_num_due_list_child_health = models.IntegerField(blank=True, null=True)
    infra_type_of_building = models.TextField(blank=True, null=True)
    infra_clean_water = models.IntegerField(blank=True, null=True)
    infra_functional_toilet = models.IntegerField(blank=True, null=True)
    infra_adult_weighing_scale = models.IntegerField(blank=True, null=True)
    infra_infant_weighing_scale = models.IntegerField(blank=True, null=True)
    infra_medicine_kits = models.IntegerField(blank=True, null=True)
    num_awc_infra_last_update = models.IntegerField(blank=True, null=True)
    usage_num_hh_reg = models.IntegerField(blank=True, null=True)
    usage_num_add_pregnancy = models.IntegerField(blank=True, null=True)
    cases_person_has_aadhaar_v2 = models.IntegerField(blank=True, null=True)
    cases_person_beneficiary_v2 = models.IntegerField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'agg_awc_monthly'


class AggCcsRecordMonthly(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    ccs_status = models.TextField(blank=True, null=True)
    trimester = models.TextField(blank=True, null=True)
    caste = models.TextField(blank=True, null=True)
    disabled = models.TextField(blank=True, null=True)
    minority = models.TextField(blank=True, null=True)
    resident = models.TextField(blank=True, null=True)
    valid_in_month = models.IntegerField(blank=True, null=True)
    valid_all_registered_in_month = models.IntegerField(blank=True, null=True)
    lactating = models.IntegerField(blank=True, null=True)
    pregnant = models.IntegerField(blank=True, null=True)
    lactating_all = models.IntegerField(blank=True, null=True)
    pregnant_all = models.IntegerField(blank=True, null=True)
    thr_eligible = models.IntegerField(blank=True, null=True)
    rations_21_plus_distributed = models.IntegerField(blank=True, null=True)
    tetanus_complete = models.IntegerField(blank=True, null=True)
    delivered_in_month = models.IntegerField(blank=True, null=True)
    anc1_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc2_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc3_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc4_received_at_delivery = models.IntegerField(blank=True, null=True)
    registration_trimester_at_delivery = models.DecimalField(
        max_digits=65535,
        decimal_places=65535,
        blank=True,
        null=True
    )
    institutional_delivery_in_month = models.IntegerField(blank=True, null=True)
    using_ifa = models.IntegerField(blank=True, null=True)
    ifa_consumed_last_seven_days = models.IntegerField(blank=True, null=True)
    anemic_normal = models.IntegerField(blank=True, null=True)
    anemic_moderate = models.IntegerField(blank=True, null=True)
    anemic_severe = models.IntegerField(blank=True, null=True)
    anemic_unknown = models.IntegerField(blank=True, null=True)
    extra_meal = models.IntegerField(blank=True, null=True)
    resting_during_pregnancy = models.IntegerField(blank=True, null=True)
    bp1_complete = models.IntegerField(blank=True, null=True)
    bp2_complete = models.IntegerField(blank=True, null=True)
    bp3_complete = models.IntegerField(blank=True, null=True)
    pnc_complete = models.IntegerField(blank=True, null=True)
    trimester_2 = models.IntegerField(blank=True, null=True)
    trimester_3 = models.IntegerField(blank=True, null=True)
    postnatal = models.IntegerField(blank=True, null=True)
    counsel_bp_vid = models.IntegerField(blank=True, null=True)
    counsel_preparation = models.IntegerField(blank=True, null=True)
    counsel_immediate_bf = models.IntegerField(blank=True, null=True)
    counsel_fp_vid = models.IntegerField(blank=True, null=True)
    counsel_immediate_conception = models.IntegerField(blank=True, null=True)
    counsel_accessible_postpartum_fp = models.IntegerField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'agg_ccs_record_monthly'


class AggChildHealthMonthly(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    month_display = models.TextField(blank=True, null=True)
    gender = models.TextField(blank=True, null=True)
    age_tranche = models.TextField(blank=True, null=True)
    caste = models.TextField(blank=True, null=True)
    minority = models.TextField(blank=True, null=True)
    resident = models.TextField(blank=True, null=True)
    valid_in_month = models.IntegerField(blank=True, null=True)
    valid_all_registered_in_month = models.IntegerField(blank=True, null=True)
    nutrition_status_weighed = models.IntegerField(blank=True, null=True)
    nutrition_status_unweighed = models.IntegerField(blank=True, null=True)
    nutrition_status_normal = models.IntegerField(blank=True, null=True)
    nutrition_status_moderately_underweight = models.IntegerField(blank=True, null=True)
    nutrition_status_severely_underweight = models.IntegerField(blank=True, null=True)
    wer_eligible = models.IntegerField(blank=True, null=True)
    height_measured_in_month = models.IntegerField(blank=True, null=True)
    height_eligible = models.IntegerField(blank=True, null=True)
    wasting_moderate = models.IntegerField(blank=True, null=True)
    wasting_severe = models.IntegerField(blank=True, null=True)
    wasting_normal = models.IntegerField(blank=True, null=True)
    wasting_moderate_v2 = models.IntegerField(blank=True, null=True)
    wasting_severe_v2 = models.IntegerField(blank=True, null=True)
    wasting_normal_v2 = models.IntegerField(blank=True, null=True)
    stunting_moderate = models.IntegerField(blank=True, null=True)
    stunting_severe = models.IntegerField(blank=True, null=True)
    stunting_normal = models.IntegerField(blank=True, null=True)
    zscore_grading_hfa_moderate = models.IntegerField(blank=True, null=True)
    zscore_grading_hfa_severe = models.IntegerField(blank=True, null=True)
    zscore_grading_hfa_normal = models.IntegerField(blank=True, null=True)
    pnc_eligible = models.IntegerField(blank=True, null=True)
    thr_eligible = models.IntegerField(blank=True, null=True)
    rations_21_plus_distributed = models.IntegerField(blank=True, null=True)
    born_in_month = models.IntegerField(blank=True, null=True)
    low_birth_weight_in_month = models.IntegerField(blank=True, null=True)
    bf_at_birth = models.IntegerField(blank=True, null=True)
    ebf_eligible = models.IntegerField(blank=True, null=True)
    ebf_in_month = models.IntegerField(blank=True, null=True)
    cf_initiation_in_month = models.IntegerField(blank=True, null=True)
    cf_initiation_eligible = models.IntegerField(blank=True, null=True)
    cf_eligible = models.IntegerField(blank=True, null=True)
    cf_in_month = models.IntegerField(blank=True, null=True)
    cf_diet_diversity = models.IntegerField(blank=True, null=True)
    cf_diet_quantity = models.IntegerField(blank=True, null=True)
    cf_demo = models.IntegerField(blank=True, null=True)
    cf_handwashing = models.IntegerField(blank=True, null=True)
    counsel_increase_food_bf = models.IntegerField(blank=True, null=True)
    counsel_manage_breast_problems = models.IntegerField(blank=True, null=True)
    counsel_ebf = models.IntegerField(blank=True, null=True)
    counsel_adequate_bf = models.IntegerField(blank=True, null=True)
    counsel_pediatric_ifa = models.IntegerField(blank=True, null=True)
    fully_immunized_eligible = models.IntegerField(blank=True, null=True)
    fully_immunized_on_time = models.IntegerField(blank=True, null=True)
    fully_immunized_late = models.IntegerField(blank=True, null=True)
    weighed_and_height_measured_in_month = models.IntegerField(blank=True, null=True)
    weighed_and_born_in_month = models.IntegerField(blank=True, null=True)
    days_ration_given_child = models.IntegerField(blank=True, null=True)
    zscore_grading_hfa_recorded_in_month = models.IntegerField(blank=True, null=True)
    zscore_grading_wfh_recorded_in_month = models.IntegerField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'agg_child_health_monthly'


class AwcLocationMonths(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    month_display = models.TextField(blank=True, null=True)
    aww_name = models.TextField(blank=True, null=True)
    contact_phone_number = models.TextField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'awc_location_months'

