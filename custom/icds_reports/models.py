from __future__ import absolute_import

from __future__ import unicode_literals
from dateutil.relativedelta import relativedelta
from django.db import connections, models

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.routers import db_for_read_write
from custom.icds_reports.utils.aggregation import (
    ComplementaryFormsAggregationHelper,
    PostnatalCareFormsChildHealthAggregationHelper,
)


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

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'awc_location'
        unique_together = (('state_id', 'district_id', 'block_id', 'supervisor_id', 'doc_id'),)


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
    cases_person_adolescent_girls_11_18 = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_11_18_all = models.IntegerField(blank=True, null=True)
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


class AggAwcMonthly(models.Model):
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
    is_launched = models.TextField(blank=True, null=True)
    num_awcs = models.IntegerField(blank=True, null=True)
    num_launched_states = models.IntegerField(blank=True, null=True)
    num_launched_districts = models.IntegerField(blank=True, null=True)
    num_launched_blocks = models.IntegerField(blank=True, null=True)
    num_launched_supervisors = models.IntegerField(blank=True, null=True)
    num_launched_awcs = models.IntegerField(blank=True, null=True)
    awc_days_open = models.IntegerField(blank=True, null=True)
    total_eligible_children = models.IntegerField(blank=True, null=True)
    total_attended_children = models.IntegerField(blank=True, null=True)
    pse_avg_attendance_percent = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    pse_full = models.IntegerField(blank=True, null=True)
    pse_partial = models.IntegerField(blank=True, null=True)
    pse_non = models.IntegerField(blank=True, null=True)
    pse_score = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    awc_days_provided_breakfast = models.IntegerField(blank=True, null=True)
    awc_days_provided_hotmeal = models.IntegerField(blank=True, null=True)
    awc_days_provided_thr = models.IntegerField(blank=True, null=True)
    awc_days_provided_pse = models.IntegerField(blank=True, null=True)
    awc_days_pse_conducted = models.IntegerField(blank=True, null=True)
    awc_not_open_holiday = models.IntegerField(blank=True, null=True)
    awc_not_open_festival = models.IntegerField(blank=True, null=True)
    awc_not_open_no_help = models.IntegerField(blank=True, null=True)
    awc_not_open_department_work = models.IntegerField(blank=True, null=True)
    awc_not_open_other = models.IntegerField(blank=True, null=True)
    awc_num_open = models.IntegerField(blank=True, null=True)
    awc_not_open_no_data = models.IntegerField(blank=True, null=True)
    wer_weighed = models.IntegerField(blank=True, null=True)
    wer_eligible = models.IntegerField(blank=True, null=True)
    wer_score = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    thr_eligible_child = models.IntegerField(blank=True, null=True)
    thr_rations_21_plus_distributed_child = models.IntegerField(blank=True, null=True)
    thr_eligible_ccs = models.IntegerField(blank=True, null=True)
    thr_rations_21_plus_distributed_ccs = models.IntegerField(blank=True, null=True)
    thr_score = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    awc_score = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    num_awc_rank_functional = models.IntegerField(blank=True, null=True)
    num_awc_rank_semi = models.IntegerField(blank=True, null=True)
    num_awc_rank_non = models.IntegerField(blank=True, null=True)
    cases_household = models.IntegerField(blank=True, null=True)
    cases_person = models.IntegerField(blank=True, null=True)
    cases_person_all = models.IntegerField(blank=True, null=True)
    cases_person_has_aadhaar = models.IntegerField(blank=True, null=True)
    cases_person_beneficiary = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_11_14 = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_15_18 = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_11_14_all = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_15_18_all = models.IntegerField(blank=True, null=True)
    cases_person_referred = models.IntegerField(blank=True, null=True)
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
    usage_awc_num_active = models.IntegerField(blank=True, null=True)
    usage_time_pse = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    usage_time_gmp = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    usage_time_bp = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    usage_time_pnc = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    usage_time_ebf = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    usage_time_cf = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    usage_time_of_day_pse = models.TimeField(blank=True, null=True)
    usage_time_of_day_home_visit = models.TimeField(blank=True, null=True)
    vhnd_immunization = models.IntegerField(blank=True, null=True)
    vhnd_anc = models.IntegerField(blank=True, null=True)
    vhnd_gmp = models.IntegerField(blank=True, null=True)
    vhnd_num_pregnancy = models.IntegerField(blank=True, null=True)
    vhnd_num_lactating = models.IntegerField(blank=True, null=True)
    vhnd_num_mothers_6_12 = models.IntegerField(blank=True, null=True)
    vhnd_num_mothers_12 = models.IntegerField(blank=True, null=True)
    vhnd_num_fathers = models.IntegerField(blank=True, null=True)
    ls_supervision_visit = models.IntegerField(blank=True, null=True)
    ls_num_supervised = models.IntegerField(blank=True, null=True)
    ls_awc_location_long = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    ls_awc_location_lat = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    ls_awc_present = models.IntegerField(blank=True, null=True)
    ls_awc_open = models.IntegerField(blank=True, null=True)
    ls_awc_not_open_aww_not_available = models.IntegerField(blank=True, null=True)
    ls_awc_not_open_closed_early = models.IntegerField(blank=True, null=True)
    ls_awc_not_open_holiday = models.IntegerField(blank=True, null=True)
    ls_awc_not_open_unknown = models.IntegerField(blank=True, null=True)
    ls_awc_not_open_other = models.IntegerField(blank=True, null=True)
    infra_last_update_date = models.DateField(blank=True, null=True)
    infra_type_of_building = models.TextField(blank=True, null=True)
    infra_type_of_building_pucca = models.IntegerField(blank=True, null=True)
    infra_type_of_building_semi_pucca = models.IntegerField(blank=True, null=True)
    infra_type_of_building_kuccha = models.IntegerField(blank=True, null=True)
    infra_type_of_building_partial_covered_space = models.IntegerField(blank=True, null=True)
    infra_clean_water = models.IntegerField(blank=True, null=True)
    infra_functional_toilet = models.IntegerField(blank=True, null=True)
    infra_baby_weighing_scale = models.IntegerField(blank=True, null=True)
    infra_flat_weighing_scale = models.IntegerField(blank=True, null=True)
    infra_adult_weighing_scale = models.IntegerField(blank=True, null=True)
    infra_infant_weighing_scale = models.IntegerField(blank=True, null=True)
    infra_cooking_utensils = models.IntegerField(blank=True, null=True)
    infra_medicine_kits = models.IntegerField(blank=True, null=True)
    infra_adequate_space_pse = models.IntegerField(blank=True, null=True)
    num_awc_infra_last_update = models.IntegerField(blank=True, null=True)
    usage_num_hh_reg = models.IntegerField(blank=True, null=True)
    usage_num_add_person = models.IntegerField(blank=True, null=True)
    usage_num_add_pregnancy = models.IntegerField(blank=True, null=True)
    training_phase = models.IntegerField(blank=True, null=True)
    trained_phase_1 = models.IntegerField(blank=True, null=True)
    trained_phase_2 = models.IntegerField(blank=True, null=True)
    trained_phase_3 = models.IntegerField(blank=True, null=True)
    trained_phase_4 = models.IntegerField(blank=True, null=True)
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
    disabled = models.TextField(blank=True, null=True)
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
    stunting_moderate = models.IntegerField(blank=True, null=True)
    stunting_severe = models.IntegerField(blank=True, null=True)
    stunting_normal = models.IntegerField(blank=True, null=True)
    pnc_eligible = models.IntegerField(blank=True, null=True)
    thr_eligible = models.IntegerField(blank=True, null=True)
    rations_21_plus_distributed = models.IntegerField(blank=True, null=True)
    pse_eligible = models.IntegerField(blank=True, null=True)
    pse_attended_16_days = models.IntegerField(blank=True, null=True)
    born_in_month = models.IntegerField(blank=True, null=True)
    low_birth_weight_in_month = models.IntegerField(blank=True, null=True)
    bf_at_birth = models.IntegerField(blank=True, null=True)
    ebf_eligible = models.IntegerField(blank=True, null=True)
    ebf_in_month = models.IntegerField(blank=True, null=True)
    ebf_no_info_recorded = models.IntegerField(blank=True, null=True)
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
    counsel_play_cf_video = models.IntegerField(blank=True, null=True)
    fully_immunized_eligible = models.IntegerField(blank=True, null=True)
    fully_immunized_on_time = models.IntegerField(blank=True, null=True)
    fully_immunized_late = models.IntegerField(blank=True, null=True)
    weighed_and_height_measured_in_month = models.IntegerField(blank=True, null=True)
    weighed_and_born_in_month = models.IntegerField(blank=True, null=True)

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

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'awc_location_months'


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
    case_id = models.TextField(primary_key=True)
    awc_id = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    person_name = models.TextField(blank=True, null=True)
    mother_name = models.TextField(blank=True, null=True)
    opened_on = models.DateField(blank=True, null=True)
    closed_on = models.DateField(blank=True, null=True)
    closed = models.IntegerField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    sex = models.TextField(blank=True, null=True)
    fully_immunized_date = models.DateField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    age_in_months = models.IntegerField(blank=True, null=True)
    open_in_month = models.IntegerField(blank=True, null=True)
    valid_in_month = models.IntegerField(blank=True, null=True)
    wer_eligible = models.IntegerField(blank=True, null=True)
    valid_all_registered_in_month = models.IntegerField(blank=True, null=True)
    nutrition_status_last_recorded = models.TextField(blank=True, null=True)
    current_month_nutrition_status = models.TextField(blank=True, null=True)
    nutrition_status_weighed = models.IntegerField(blank=True, null=True)
    num_rations_distributed = models.IntegerField(blank=True, null=True)
    pse_eligible = models.IntegerField(blank=True, null=True)
    pse_days_attended = models.IntegerField(blank=True, null=True)
    born_in_month = models.IntegerField(blank=True, null=True)
    recorded_weight = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    recorded_height = models.DecimalField(max_digits=65535, decimal_places=65535, blank=True, null=True)
    thr_eligible = models.IntegerField(blank=True, null=True)
    stunting_last_recorded = models.TextField(blank=True, null=True)
    current_month_stunting = models.TextField(blank=True, null=True)
    wasting_last_recorded = models.TextField(blank=True, null=True)
    current_month_wasting = models.TextField(blank=True, null=True)
    fully_immunized = models.IntegerField(blank=True, null=True)

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'child_health_monthly_view'


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

    class Meta(object):
        app_label = 'icds_model'
        managed = False
        db_table = 'ccs_record_monthly'


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
        db_table = 'icds_dashboard_comp_feed_form'

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
        help_text="Counseling on increasing food intake has ever been completed"
    )
    counsel_breast = models.PositiveSmallIntegerField(
        help_text="Counseling on managing breast problems has ever been completed"
    )
    skin_to_skin = models.PositiveSmallIntegerField(
        help_text="Counseling on skin to skin care has ever been completed"
    )
    is_ebf = models.PositiveSmallIntegerField(
        help_text="is_ebf set in the last form submitted this month"
    )
    water_or_milk = models.PositiveSmallIntegerField(
        help_text="Child given water or milk in the last form submitted this month"
    )
    other_milk_to_child = models.PositiveSmallIntegerField(
        help_text="Child given something other than milk in the last form submitted this month"
    )
    tea_other = models.PositiveSmallIntegerField(
        help_text="Child given tea or other liquid in the last form submitted this month"
    )
    eating = models.PositiveSmallIntegerField(
        help_text="Child given something to eat in the last form submitted this month"
    )
    counsel_exclusive_bf = models.PositiveSmallIntegerField(
        help_text="Counseling about exclusive breastfeeding has ever occurred"
    )
    counsel_only_milk = models.PositiveSmallIntegerField(
        help_text="Counseling about avoiding other than breast milk has ever occurred"
    )
    counsel_adequate_bf = models.PositiveSmallIntegerField(
        help_text="Counseling about adequate breastfeeding has ever occurred"
    )
    not_breastfeeding = models.CharField(
        help_text="The reason the mother is not able to breastfeed"
    )

    class Meta(object):
        db_table = 'icds_dashboard_child_health_postnatal_forms'

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
