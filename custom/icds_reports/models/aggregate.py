from __future__ import absolute_import, unicode_literals

from contextlib import contextmanager
from datetime import date

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.routers import db_for_read_write
from custom.icds_reports.const import (AGG_CCS_RECORD_BP_TABLE,
    AGG_CCS_RECORD_CF_TABLE, AGG_CCS_RECORD_DELIVERY_TABLE,
    AGG_CCS_RECORD_PNC_TABLE, AGG_CCS_RECORD_THR_TABLE,
    AGG_CHILD_HEALTH_PNC_TABLE, AGG_CHILD_HEALTH_THR_TABLE,
    AGG_COMP_FEEDING_TABLE, AGG_DAILY_FEEDING_TABLE,
    AGG_GROWTH_MONITORING_TABLE, AGG_INFRASTRUCTURE_TABLE, AWW_INCENTIVE_TABLE,
                                       AGG_LS_AWC_VISIT_TABLE, AGG_LS_VHND_TABLE,
                                       AGG_LS_BENEFICIARY_TABLE, AGG_THR_V2_TABLE)
from django.db import connections, models, transaction

from custom.icds_reports.models.manager import CitusComparisonManager
from custom.icds_reports.utils.aggregation_helpers.helpers import get_helper
from custom.icds_reports.utils.aggregation_helpers.monolith import (
    AggCcsRecordAggregationHelper,
    AggChildHealthAggregationHelper,
    AwcInfrastructureAggregationHelper,
    AwwIncentiveAggregationHelper,
    LSAwcMgtFormAggHelper,
    LSBeneficiaryFormAggHelper,
    LSVhndFormAggHelper,
    AggLsHelper,
    BirthPreparednessFormsAggregationHelper,
    CcsRecordMonthlyAggregationHelper,
    ChildHealthMonthlyAggregationHelper,
    ComplementaryFormsAggregationHelper,
    ComplementaryFormsCcsRecordAggregationHelper,
    DailyFeedingFormsChildHealthAggregationHelper,
    DeliveryFormsAggregationHelper,
    GrowthMonitoringFormsAggregationHelper,
    InactiveAwwsAggregationHelper,
    PostnatalCareFormsCcsRecordAggregationHelper,
    PostnatalCareFormsChildHealthAggregationHelper,
    THRFormsChildHealthAggregationHelper,
    THRFormsCcsRecordAggregationHelper,
    AggAwcHelper,
    AggAwcDailyAggregationHelper,
    LocationAggregationHelper,
    DailyAttendanceAggregationHelper,
    THRFormV2AggHelper
)


def get_cursor(model):
    db = db_for_read_write(model)
    return connections[db].cursor()


def maybe_atomic(cls, atomic=True):
    if atomic:
        return transaction.atomic(using=db_for_read_write(cls))
    else:
        @contextmanager
        def noop_context():
            yield

        return noop_context()


class AggregateMixin(object):
    _agg_helper_cls = None
    _agg_atomic = True

    @classmethod
    def aggregate(cls, *args, **kwargs):
        helper = cls._get_helper(*args, **kwargs)
        with get_cursor(cls) as cursor, maybe_atomic(cls, cls._agg_atomic):
            helper.aggregate(cursor)

    @classmethod
    def _get_helper(cls, *args, **kwargs):
        helper_cls = get_helper(cls._agg_helper_cls.helper_key)
        return helper_cls(*args, **kwargs)


class CcsRecordMonthly(models.Model, AggregateMixin):
    supervisor_id = models.TextField()
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
    institutional_delivery = models.IntegerField(blank=True, null=True)
    add = models.DateField(blank=True, null=True)
    anc_in_month = models.SmallIntegerField(blank=True, null=True)
    caste = models.TextField(blank=True, null=True)
    disabled = models.TextField(blank=True, null=True)
    minority = models.TextField(blank=True, null=True)
    resident = models.TextField(blank=True, null=True)
    anc_weight = models.SmallIntegerField(blank=True, null=True)
    anc_blood_pressure = models.SmallIntegerField(blank=True, null=True)
    bp_sys = models.SmallIntegerField(blank=True, null=True)
    bp_dia = models.SmallIntegerField(blank=True, null=True)
    anc_hemoglobin = models.DecimalField(max_digits=64, decimal_places=20, blank=True, null=True)
    bleeding = models.SmallIntegerField(blank=True, null=True)
    swelling = models.SmallIntegerField(blank=True, null=True)
    blurred_vision = models.SmallIntegerField(blank=True, null=True)
    convulsions = models.SmallIntegerField(blank=True, null=True)
    rupture = models.SmallIntegerField(blank=True, null=True)
    anemia = models.SmallIntegerField(blank=True, null=True)
    eating_extra = models.SmallIntegerField(blank=True, null=True)
    resting = models.SmallIntegerField(blank=True, null=True)
    immediate_breastfeeding = models.SmallIntegerField(blank=True, null=True)
    person_name = models.TextField(blank=True, null=True)
    edd = models.DateField(blank=True, null=True)
    delivery_nature = models.SmallIntegerField(blank=True, null=True)
    is_ebf = models.SmallIntegerField(blank=True, null=True)
    breastfed_at_birth = models.SmallIntegerField(blank=True, null=True)
    anc_1 = models.DateField(blank=True, null=True)
    anc_2 = models.DateField(blank=True, null=True)
    anc_3 = models.DateField(blank=True, null=True)
    anc_4 = models.DateField(blank=True, null=True)
    tt_1 = models.DateField(blank=True, null=True)
    tt_2 = models.DateField(blank=True, null=True)
    valid_in_month = models.SmallIntegerField(blank=True, null=True)
    mobile_number = models.TextField(blank=True, null=True)
    preg_order = models.SmallIntegerField(blank=True, null=True)
    home_visit_date = models.DateField(
        blank=True,
        null=True,
        help_text='date of last bp visit in month'
    )
    num_pnc_visits = models.SmallIntegerField(blank=True, null=True)
    last_date_thr = models.DateField(blank=True, null=True)
    num_anc_complete = models.SmallIntegerField(blank=True, null=True)
    opened_on = models.DateField(blank=True, null=True)
    valid_visits = models.SmallIntegerField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    closed = models.SmallIntegerField(blank=True, null=True)
    anc_abnormalities = models.SmallIntegerField(blank=True, null=True)
    date_death = models.DateField(blank=True, null=True)
    person_case_id = models.TextField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        managed = False
        db_table = 'ccs_record_monthly'
        unique_together = ('supervisor_id', 'month', 'case_id')

    _agg_helper_cls = CcsRecordMonthlyAggregationHelper
    _agg_atomic = True


class AwcLocation(models.Model, AggregateMixin):
    doc_id = models.TextField()
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(db_index=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(db_index=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(db_index=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(db_index=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True, db_index=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    state_is_test = models.SmallIntegerField(blank=True, null=True)
    district_is_test = models.SmallIntegerField(blank=True, null=True)
    block_is_test = models.SmallIntegerField(blank=True, null=True)
    supervisor_is_test = models.SmallIntegerField(blank=True, null=True)
    awc_is_test = models.SmallIntegerField(blank=True, null=True)

    # from commcare-user case
    aww_name = models.TextField(blank=True, null=True)
    contact_phone_number = models.TextField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        managed = False
        db_table = 'awc_location'
        unique_together = (('state_id', 'district_id', 'block_id', 'supervisor_id', 'doc_id'),)

    _agg_helper_cls = LocationAggregationHelper
    _agg_atomic = False


class AwcLocationLocal(AwcLocation):

    objects = models.Manager()

    class Meta(object):
        managed = False
        db_table = 'awc_location_local'


class ChildHealthMonthly(models.Model, AggregateMixin):
    supervisor_id = models.TextField()
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
    recorded_weight = models.DecimalField(max_digits=64, decimal_places=20, blank=True, null=True)
    recorded_height = models.DecimalField(max_digits=64, decimal_places=20, blank=True, null=True)
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
    mother_name = models.TextField(blank=True, null=True)
    immunization_in_month = models.SmallIntegerField(blank=True, null=True)
    days_ration_given_child = models.SmallIntegerField(blank=True, null=True)
    zscore_grading_hfa = models.SmallIntegerField(blank=True, null=True)
    zscore_grading_hfa_recorded_in_month = models.SmallIntegerField(blank=True, null=True)
    zscore_grading_wfh = models.SmallIntegerField(blank=True, null=True)
    zscore_grading_wfh_recorded_in_month = models.SmallIntegerField(blank=True, null=True)
    muac_grading = models.SmallIntegerField(blank=True, null=True)
    muac_grading_recorded_in_month = models.SmallIntegerField(blank=True, null=True)
    mother_phone_number = models.TextField(blank=True, null=True)
    date_death = models.DateField(blank=True, null=True)
    mother_case_id = models.TextField(blank=True, null=True)
    lunch_count = models.IntegerField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta:
        managed = False
        db_table = 'child_health_monthly'
        unique_together = ('supervisor_id', 'case_id', 'month')

    _agg_helper_cls = ChildHealthMonthlyAggregationHelper
    _agg_atomic = False


class AggAwc(models.Model, AggregateMixin):
    state_id = models.TextField()
    district_id = models.TextField()
    block_id = models.TextField()
    supervisor_id = models.TextField()
    awc_id = models.TextField()
    month = models.DateField()
    num_awcs = models.SmallIntegerField()
    awc_days_open = models.SmallIntegerField(null=True)
    total_eligible_children = models.SmallIntegerField(null=True)
    total_attended_children = models.SmallIntegerField(null=True)
    pse_avg_attendance_percent = models.DecimalField(max_digits=64, decimal_places=20, null=True)
    pse_full = models.IntegerField(null=True)
    pse_partial = models.IntegerField(null=True)
    pse_non = models.IntegerField(null=True)
    pse_score = models.DecimalField(max_digits=64, decimal_places=20, null=True)
    awc_days_provided_breakfast = models.IntegerField(null=True)
    awc_days_provided_hotmeal = models.IntegerField(null=True)
    awc_days_provided_thr = models.IntegerField(null=True)
    awc_days_provided_pse = models.IntegerField(null=True)
    awc_not_open_holiday = models.IntegerField(null=True)
    awc_not_open_festival = models.IntegerField(null=True)
    awc_not_open_no_help = models.IntegerField(null=True)
    awc_not_open_department_work = models.IntegerField(null=True)
    awc_not_open_other = models.IntegerField(null=True)
    awc_num_open = models.IntegerField(null=True)
    awc_not_open_no_data = models.IntegerField(null=True)
    wer_weighed = models.IntegerField(null=True)
    wer_weighed_0_2 = models.IntegerField(null=True)
    wer_eligible = models.IntegerField(null=True)
    wer_eligible_0_2 = models.IntegerField(null=True)
    wer_score = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    thr_eligible_child = models.IntegerField(null=True)
    thr_rations_21_plus_distributed_child = models.IntegerField(null=True)
    thr_eligible_ccs = models.IntegerField(null=True)
    thr_rations_21_plus_distributed_ccs = models.IntegerField(null=True)
    thr_score = models.DecimalField(max_digits=64, decimal_places=20, null=True)
    awc_score = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    num_awc_rank_functional = models.IntegerField(null=True)
    num_awc_rank_semi = models.IntegerField(null=True)
    num_awc_rank_non = models.IntegerField(null=True)
    cases_ccs_pregnant = models.IntegerField(null=True)
    cases_ccs_lactating = models.IntegerField(null=True)
    cases_child_health = models.IntegerField(null=True)
    usage_num_pse = models.IntegerField(null=True)
    usage_num_gmp = models.IntegerField(null=True)
    usage_num_thr = models.IntegerField(null=True)
    usage_num_home_visit = models.IntegerField(null=True)
    usage_num_bp_tri1 = models.IntegerField(null=True)
    usage_num_bp_tri2 = models.IntegerField(null=True)
    usage_num_bp_tri3 = models.IntegerField(null=True)
    usage_num_pnc = models.IntegerField(null=True)
    usage_num_ebf = models.IntegerField(null=True)
    usage_num_cf = models.IntegerField(null=True)
    usage_num_delivery = models.IntegerField(null=True)
    usage_num_due_list_ccs = models.IntegerField(null=True)
    usage_num_due_list_child_health = models.IntegerField(null=True)
    usage_awc_num_active = models.IntegerField(null=True)
    usage_time_pse = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    usage_time_gmp = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    usage_time_bp = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    usage_time_pnc = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    usage_time_ebf = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    usage_time_cf = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    usage_time_of_day_pse = models.TimeField(null=True)
    usage_time_of_day_home_visit = models.TimeField(null=True)
    vhnd_immunization = models.IntegerField(null=True)
    vhnd_anc = models.IntegerField(null=True)
    vhnd_gmp = models.IntegerField(null=True)
    vhnd_num_pregnancy = models.IntegerField(null=True)
    vhnd_num_lactating = models.IntegerField(null=True)
    vhnd_num_mothers_6_12 = models.IntegerField(null=True)
    vhnd_num_mothers_12 = models.IntegerField(null=True)
    vhnd_num_fathers = models.IntegerField(null=True)
    ls_supervision_visit = models.IntegerField(null=True)
    ls_num_supervised = models.IntegerField(null=True)
    ls_awc_location_long = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    ls_awc_location_lat = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    ls_awc_present = models.IntegerField(null=True)
    ls_awc_open = models.IntegerField(null=True)
    ls_awc_not_open_aww_not_available = models.IntegerField(null=True)
    ls_awc_not_open_closed_early = models.IntegerField(null=True)
    ls_awc_not_open_holiday = models.IntegerField(null=True)
    ls_awc_not_open_unknown = models.IntegerField(null=True)
    ls_awc_not_open_other = models.IntegerField(null=True)
    infra_last_update_date = models.DateField(null=True)
    infra_type_of_building = models.TextField(null=True)
    infra_type_of_building_pucca = models.IntegerField(null=True)
    infra_type_of_building_semi_pucca = models.IntegerField(null=True)
    infra_type_of_building_kuccha = models.IntegerField(null=True)
    infra_type_of_building_partial_covered_space = models.IntegerField(null=True)
    infra_clean_water = models.IntegerField(null=True)
    infra_functional_toilet = models.IntegerField(null=True)
    infra_baby_weighing_scale = models.IntegerField(null=True)
    infra_flat_weighing_scale = models.IntegerField(null=True)
    infra_adult_weighing_scale = models.IntegerField(null=True)
    infra_cooking_utensils = models.IntegerField(null=True)
    infra_medicine_kits = models.IntegerField(null=True)
    infra_adequate_space_pse = models.IntegerField(null=True)
    cases_person_beneficiary = models.IntegerField(null=True)
    cases_person_referred = models.IntegerField(null=True)
    awc_days_pse_conducted = models.IntegerField(null=True)
    num_awc_infra_last_update = models.IntegerField(null=True)
    cases_person_has_aadhaar_v2 = models.IntegerField(null=True)
    cases_person_beneficiary_v2 = models.IntegerField(null=True)
    electricity_awc = models.IntegerField(null=True)
    infantometer = models.IntegerField(null=True)
    stadiometer = models.IntegerField(null=True)
    num_anc_visits = models.IntegerField(null=True)
    num_children_immunized = models.IntegerField(null=True)
    usage_num_hh_reg = models.IntegerField(null=True)
    usage_num_add_person = models.IntegerField(null=True)
    usage_num_add_pregnancy = models.IntegerField(null=True)
    is_launched = models.TextField(null=True)
    training_phase = models.IntegerField(null=True)
    trained_phase_1 = models.IntegerField(null=True)
    trained_phase_2 = models.IntegerField(null=True)
    trained_phase_3 = models.IntegerField(null=True)
    trained_phase_4 = models.IntegerField(null=True)
    aggregation_level = models.IntegerField(null=True)
    num_launched_states = models.IntegerField(null=True)
    num_launched_districts = models.IntegerField(null=True)
    num_launched_blocks = models.IntegerField(null=True)
    num_launched_supervisors = models.IntegerField(null=True)
    num_launched_awcs = models.IntegerField(null=True)

    num_awcs_conducted_cbe = models.IntegerField(null=True)
    num_awcs_conducted_vhnd = models.IntegerField(null=True)

    cases_household = models.IntegerField(null=True)
    cases_person = models.IntegerField(null=True)
    cases_person_all = models.IntegerField(null=True)
    cases_person_has_aadhaar = models.IntegerField(null=True)
    cases_ccs_pregnant_all = models.IntegerField(null=True)
    cases_ccs_lactating_all = models.IntegerField(null=True)
    cases_child_health_all = models.IntegerField(null=True)
    cases_person_adolescent_girls_11_14 = models.IntegerField(null=True)
    cases_person_adolescent_girls_15_18 = models.IntegerField(null=True)
    cases_person_adolescent_girls_11_14_all = models.IntegerField(null=True)
    cases_person_adolescent_girls_15_18_all = models.IntegerField(null=True)
    infra_infant_weighing_scale = models.IntegerField(null=True)
    state_is_test = models.SmallIntegerField(blank=True, null=True)
    district_is_test = models.SmallIntegerField(blank=True, null=True)
    block_is_test = models.SmallIntegerField(blank=True, null=True)
    supervisor_is_test = models.SmallIntegerField(blank=True, null=True)
    awc_is_test = models.SmallIntegerField(blank=True, null=True)
    valid_visits = models.IntegerField(null=True)
    expected_visits = models.IntegerField(null=True)
    thr_distribution_image_count = models.IntegerField(null=True)

    objects = CitusComparisonManager()

    class Meta:
        managed = False
        db_table = 'agg_awc'

    @classmethod
    def weekly_aggregate(cls, month):
        helper = AggAwcHelper(month)
        with get_cursor(cls) as cursor:
            helper.weekly_aggregate(cursor)

    _agg_helper_cls = AggAwcHelper
    _agg_atomic = False


class AggregateLsAWCVisitForm(models.Model, AggregateMixin):
    awc_visits = models.IntegerField(help_text='awc visits made by LS')
    month = models.DateField()
    supervisor_id = models.TextField()
    state_id = models.TextField()

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_LS_AWC_VISIT_TABLE

    _agg_helper_cls = LSAwcMgtFormAggHelper
    _agg_atomic = False


class AggregateLsVhndForm(models.Model, AggregateMixin):
    vhnd_observed = models.IntegerField(help_text='VHND forms submitted by LS')
    month = models.DateField()
    supervisor_id = models.TextField()
    state_id = models.TextField()

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_LS_VHND_TABLE

    _agg_helper_cls = LSVhndFormAggHelper
    _agg_atomic = False


class AggregateBeneficiaryForm(models.Model, AggregateMixin):
    beneficiary_vists = models.IntegerField(help_text='Beneficiary visits done by LS')
    month = models.DateField()
    supervisor_id = models.TextField()
    state_id = models.TextField()

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_LS_BENEFICIARY_TABLE

    _agg_helper_cls = LSBeneficiaryFormAggHelper
    _agg_atomic = False


class AggLs(models.Model, AggregateMixin):
    """
    Model refers to the agg_ls table in database.
    Table contains the aggregated data from LS ucrs.
    """
    awc_visits = models.IntegerField(help_text='awc visits made by LS')
    vhnd_observed = models.IntegerField(help_text='VHND forms submitted by LS')
    beneficiary_vists = models.IntegerField(help_text='Beneficiary visits done by LS')
    month = models.DateField()
    state_id = models.TextField()
    district_id = models.TextField()
    block_id = models.TextField()
    supervisor_id = models.TextField()
    aggregation_level = models.SmallIntegerField()

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = 'agg_ls'

    _agg_helper_cls = AggLsHelper
    _agg_atomic = False


class AggregateTHRForm(models.Model, AggregateMixin):
    state_id = models.TextField()
    supervisor_id = models.TextField()
    awc_id = models.TextField()
    month = models.DateField()
    thr_distribution_image_count = models.IntegerField(help_text='Count of Images clicked per awc')

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_THR_V2_TABLE

    _agg_helper_cls = THRFormV2AggHelper
    _agg_atomic = False


class AggCcsRecord(models.Model, AggregateMixin):
    state_id = models.TextField()
    district_id = models.TextField()
    block_id = models.TextField()
    supervisor_id = models.TextField()
    awc_id = models.TextField()
    month = models.DateField()
    ccs_status = models.TextField()
    trimester = models.TextField()
    caste = models.TextField(null=True)
    disabled = models.TextField(null=True)
    minority = models.TextField(null=True)
    resident = models.TextField(null=True)
    valid_in_month = models.IntegerField()
    lactating = models.IntegerField()
    pregnant = models.IntegerField()
    thr_eligible = models.IntegerField()
    rations_21_plus_distributed = models.IntegerField()
    tetanus_complete = models.IntegerField()
    delivered_in_month = models.IntegerField()
    anc1_received_at_delivery = models.IntegerField()
    anc2_received_at_delivery = models.IntegerField()
    anc3_received_at_delivery = models.IntegerField()
    anc4_received_at_delivery = models.IntegerField()
    registration_trimester_at_delivery = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    using_ifa = models.IntegerField()
    ifa_consumed_last_seven_days = models.IntegerField()
    anemic_normal = models.IntegerField()
    anemic_moderate = models.IntegerField()
    anemic_severe = models.IntegerField()
    anemic_unknown = models.IntegerField()
    extra_meal = models.IntegerField()
    resting_during_pregnancy = models.IntegerField()
    bp1_complete = models.IntegerField()
    bp2_complete = models.IntegerField()
    bp3_complete = models.IntegerField()
    pnc_complete = models.IntegerField()
    trimester_2 = models.IntegerField()
    trimester_3 = models.IntegerField()
    postnatal = models.IntegerField()
    counsel_bp_vid = models.IntegerField()
    counsel_preparation = models.IntegerField()
    counsel_immediate_bf = models.IntegerField()
    counsel_fp_vid = models.IntegerField()
    counsel_immediate_conception = models.IntegerField()
    counsel_accessible_postpartum_fp = models.IntegerField()
    has_aadhar_id = models.IntegerField(null=True)
    aggregation_level = models.IntegerField(null=True)
    valid_all_registered_in_month = models.IntegerField(null=True)
    institutional_delivery_in_month = models.IntegerField(null=True)
    lactating_all = models.IntegerField(null=True)
    pregnant_all = models.IntegerField(null=True)
    valid_visits = models.IntegerField(null=True)
    expected_visits = models.IntegerField(null=True)

    objects = CitusComparisonManager()

    class Meta:
        managed = False
        db_table = 'agg_ccs_record'

    _agg_helper_cls = AggCcsRecordAggregationHelper
    _agg_atomic = True


class AggChildHealth(models.Model, AggregateMixin):
    state_id = models.TextField()
    district_id = models.TextField()
    block_id = models.TextField()
    supervisor_id = models.TextField()
    awc_id = models.TextField()
    month = models.DateField()
    gender = models.TextField(null=True)
    age_tranche = models.TextField(null=True)
    caste = models.TextField(null=True)
    disabled = models.TextField(null=True)
    minority = models.TextField(null=True)
    resident = models.TextField(null=True)
    valid_in_month = models.IntegerField()
    nutrition_status_weighed = models.IntegerField()
    nutrition_status_unweighed = models.IntegerField()
    nutrition_status_normal = models.IntegerField()
    nutrition_status_moderately_underweight = models.IntegerField()
    nutrition_status_severely_underweight = models.IntegerField()
    wer_eligible = models.IntegerField()
    thr_eligible = models.IntegerField()
    rations_21_plus_distributed = models.IntegerField()
    pse_eligible = models.IntegerField()
    pse_attended_16_days = models.IntegerField()
    pse_attended_21_days = models.IntegerField()
    born_in_month = models.IntegerField()
    low_birth_weight_in_month = models.IntegerField()
    bf_at_birth = models.IntegerField()
    ebf_eligible = models.IntegerField()
    ebf_in_month = models.IntegerField()
    cf_eligible = models.IntegerField()
    cf_in_month = models.IntegerField()
    cf_diet_diversity = models.IntegerField()
    cf_diet_quantity = models.IntegerField()
    cf_demo = models.IntegerField()
    cf_handwashing = models.IntegerField()
    counsel_increase_food_bf = models.IntegerField()
    counsel_manage_breast_problems = models.IntegerField()
    counsel_ebf = models.IntegerField()
    counsel_adequate_bf = models.IntegerField()
    counsel_pediatric_ifa = models.IntegerField()
    counsel_play_cf_video = models.IntegerField()
    fully_immunized_eligible = models.IntegerField()
    fully_immunized_on_time = models.IntegerField()
    fully_immunized_late = models.IntegerField()
    weighed_and_height_measured_in_month = models.IntegerField(null=True)
    weighed_and_born_in_month = models.IntegerField(null=True)
    days_ration_given_child = models.IntegerField(null=True)
    zscore_grading_hfa_normal = models.IntegerField(null=True)
    zscore_grading_hfa_moderate = models.IntegerField(null=True)
    zscore_grading_hfa_severe = models.IntegerField(null=True)
    wasting_normal_v2 = models.IntegerField(null=True)
    wasting_moderate_v2 = models.IntegerField(null=True)
    wasting_severe_v2 = models.IntegerField(null=True)
    has_aadhar_id = models.IntegerField(null=True)
    aggregation_level = models.IntegerField(null=True)
    pnc_eligible = models.IntegerField(null=True)
    height_eligible = models.IntegerField(null=True)
    wasting_moderate = models.IntegerField(null=True)
    wasting_severe = models.IntegerField(null=True)
    stunting_moderate = models.IntegerField(null=True)
    stunting_severe = models.IntegerField(null=True)
    cf_initiation_in_month = models.IntegerField(null=True)
    cf_initiation_eligible = models.IntegerField(null=True)
    height_measured_in_month = models.IntegerField(null=True)
    wasting_normal = models.IntegerField(null=True)
    stunting_normal = models.IntegerField(null=True)
    valid_all_registered_in_month = models.IntegerField(null=True)
    ebf_no_info_recorded = models.IntegerField(null=True)
    zscore_grading_hfa_recorded_in_month = models.IntegerField(blank=True, null=True)
    zscore_grading_wfh_recorded_in_month = models.IntegerField(blank=True, null=True)
    lunch_count_21_days = models.IntegerField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta:
        managed = False
        db_table = 'agg_child_health'

    _agg_helper_cls = AggChildHealthAggregationHelper
    _agg_atomic = True


class AggAwcDaily(models.Model, AggregateMixin):
    state_id = models.TextField()
    district_id = models.TextField()
    block_id = models.TextField()
    supervisor_id = models.TextField()
    awc_id = models.TextField()
    aggregation_level = models.IntegerField(null=True)
    date = models.DateField()
    cases_household = models.IntegerField(null=True)
    cases_person = models.IntegerField(null=True)
    cases_person_all = models.IntegerField(null=True)
    cases_person_has_aadhaar = models.IntegerField(null=True)
    cases_child_health = models.IntegerField(null=True)
    cases_child_health_all = models.IntegerField(null=True)
    cases_ccs_pregnant = models.IntegerField(null=True)
    cases_ccs_pregnant_all = models.IntegerField(null=True)
    cases_ccs_lactating = models.IntegerField(null=True)
    cases_ccs_lactating_all = models.IntegerField(null=True)
    cases_person_adolescent_girls_11_14 = models.IntegerField(null=True)
    cases_person_adolescent_girls_15_18 = models.IntegerField(null=True)
    cases_person_adolescent_girls_11_14_all = models.IntegerField(null=True)
    cases_person_adolescent_girls_15_18_all = models.IntegerField(null=True)
    daily_attendance_open = models.IntegerField(null=True)
    num_awcs = models.IntegerField(null=True)
    num_launched_states = models.IntegerField(null=True)
    num_launched_districts = models.IntegerField(null=True)
    num_launched_blocks = models.IntegerField(null=True)
    num_launched_supervisors = models.IntegerField(null=True)
    num_launched_awcs = models.IntegerField(null=True)
    cases_person_beneficiary = models.IntegerField(null=True)
    cases_person_has_aadhaar_v2 = models.IntegerField(null=True)
    cases_person_beneficiary_v2 = models.IntegerField(null=True)

    objects = CitusComparisonManager()

    class Meta:
        managed = False
        db_table = 'agg_awc_daily'

    _agg_helper_cls = AggAwcDailyAggregationHelper
    _agg_atomic = True


class DailyAttendance(models.Model, AggregateMixin):
    # not the real pkey - see unique_together
    doc_id = models.TextField(primary_key=True)
    awc_id = models.TextField(null=True)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(null=True)
    pse_date = models.DateField(null=True)
    awc_open_count = models.IntegerField(null=True)
    count = models.IntegerField(null=True)
    eligible_children = models.IntegerField(null=True)
    attended_children = models.IntegerField(null=True)
    attended_children_percent = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    form_location = models.TextField(null=True)
    form_location_lat = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    form_location_long = models.DecimalField(max_digits=64, decimal_places=16, null=True)
    image_name = models.TextField(null=True)
    pse_conducted = models.SmallIntegerField(null=True)

    objects = CitusComparisonManager()

    class Meta:
        managed = False
        db_table = 'daily_attendance'
        unique_together = ('supervisor_id', 'doc_id', 'month')  # pkey
        indexes = [
            models.Index(fields=['awc_id'], name='idx_daily_attendance_awc_id')
        ]

    _agg_helper_cls = DailyAttendanceAggregationHelper
    _agg_atomic = False


class AggregateComplementaryFeedingForms(models.Model, AggregateMixin):
    """Aggregated data based on AWW App, Home Visit Scheduler module,
    Complementary Feeding form.

    A child table exists for each state_id and month.

    A row exists for every case that has ever had a Complementary Feeding Form
    submitted against it.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
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

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_COMP_FEEDING_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = ComplementaryFormsAggregationHelper
    _agg_atomic = False

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        helper = ComplementaryFormsAggregationHelper(state_id, month)
        query, params = helper.compare_with_old_data_query()

        with get_cursor(AggregateComplementaryFeedingForms) as cursor:
            cursor.execute(query, params)
            rows = fetchall_as_namedtuple(cursor)
            return [row.child_health_case_id for row in rows]


class AggregateCcsRecordComplementaryFeedingForms(models.Model, AggregateMixin):
    """Aggregated data based on AWW App, Home Visit Scheduler module,
    Complementary Feeding form.

    A child table exists for each state_id and month.

    A row exists for every ccs_record case that has ever had a Complementary Feeding Form
    submitted against it.
    """
    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )

    valid_visits = models.PositiveSmallIntegerField(
        help_text="number of qualified visits for the incentive report",
        default=0
    )

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_CCS_RECORD_CF_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = ComplementaryFormsCcsRecordAggregationHelper
    _agg_atomic = False


class AggregateChildHealthPostnatalCareForms(models.Model, AggregateMixin):
    """Aggregated data for child health cases based on
    AWW App, Home Visit Scheduler module,
    Post Natal Care and Exclusive Breastfeeding forms.

    A child table exists for each state_id and month.

    A row exists for every case that has ever had a Complementary Feeding Form
    submitted against it.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)

    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
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

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_CHILD_HEALTH_PNC_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = PostnatalCareFormsChildHealthAggregationHelper
    _agg_atomic = False

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        helper = PostnatalCareFormsChildHealthAggregationHelper(state_id, month)
        query, params = helper.compare_with_old_data_query()

        with get_cursor(AggregateComplementaryFeedingForms) as cursor:
            cursor.execute(query, params)
            rows = fetchall_as_namedtuple(cursor)
            return [row.child_health_case_id for row in rows]


class AggregateCcsRecordPostnatalCareForms(models.Model, AggregateMixin):
    """Aggregated data for ccs record cases based on
    AWW App, Home Visit Scheduler module,
    Post Natal Care and Exclusive Breastfeeding forms.

    A child table exists for each state_id and month.

    A row exists for every case that has ever had a Complementary Feeding Form
    submitted against it.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )
    counsel_methods = models.PositiveSmallIntegerField(
        null=True,
        help_text="Counseling about family planning methods has ever occurred"
    )
    is_ebf = models.PositiveSmallIntegerField(
        null=True,
        help_text="Whether child was exclusively breastfed at last visit"
    )
    valid_visits = models.PositiveSmallIntegerField(
        help_text="number of qualified visits for the incentive report",
        default=0
    )

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_CCS_RECORD_PNC_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        pass

    _agg_helper_cls = PostnatalCareFormsCcsRecordAggregationHelper
    _agg_atomic = False


class AggregateChildHealthTHRForms(models.Model, AggregateMixin):
    """Aggregated data for child_health cases based on
    Take Home Ration forms

    A child table exists for each state_id and month.

    A row exists for every child_health case that has had a THR Form
    submitted against it this month.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
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
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = THRFormsChildHealthAggregationHelper
    _agg_atomic = False


class AggregateCcsRecordTHRForms(models.Model, AggregateMixin):
    """Aggregated data for ccs_record cases based on
    Take Home Ration forms

    A child table exists for each state_id and month.

    A row exists for every ccs_record case that has had a THR Form
    submitted against it this month.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )
    days_ration_given_mother = models.PositiveSmallIntegerField(
        null=True,
        help_text="Number of days the mother has been given rations this month"
    )

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_CCS_RECORD_THR_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = THRFormsCcsRecordAggregationHelper
    _agg_atomic = False


class AggregateGrowthMonitoringForms(models.Model, AggregateMixin):
    """Aggregated data based on AWW App

    376FA2E1 -> Delivery
    b183124a -> Growth Monitoring
    7a557541 -> Advanced Growth Monitoring

    A child table exists for each state_id and month.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
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

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_GROWTH_MONITORING_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = GrowthMonitoringFormsAggregationHelper
    _agg_atomic = False

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        helper = GrowthMonitoringFormsAggregationHelper(state_id, month)
        query, params = helper.compare_with_old_data_query()

        with get_cursor(cls) as cursor:
            cursor.execute(query, params)
            rows = fetchall_as_namedtuple(cursor)
            return [row.child_health_case_id for row in rows]


class AggregateBirthPreparednesForms(models.Model, AggregateMixin):
    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )

    immediate_breastfeeding = models.PositiveSmallIntegerField(
        null=True,
        help_text="Has ever had /data/bp2/immediate_breastfeeding = 'yes'"
    )
    anemia = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of /data/bp1/anemia. severe=1, moderate=2, normal=3"
    )
    eating_extra = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of /data/bp1/eating_extra = 'yes'."
    )
    resting = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of /data/bp1/resting = 'yes'."
    )
    # anc_details path is /data/bp1/iteration/item/filter/anc_details
    anc_weight = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of anc_details/anc_weight"
    )
    anc_blood_pressure = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of anc_details/anc_blood_pressure. normal=1, high=2, not_measured=3"
    )
    bp_sys = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of anc_details/bp_sys"
    )
    bp_dia = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of anc_details/bp_dia"
    )
    anc_hemoglobin = models.DecimalField(
        max_digits=64,
        decimal_places=20,
        null=True,
        help_text="Last value of anc_details/anc_hemoglobin"
    )
    bleeding = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of /data/bp2/bleeding = 'yes'"
    )
    swelling = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of /data/bp2/swelling = 'yes'"
    )
    blurred_vision = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of /data/bp2/blurred_vision = 'yes'"
    )
    convulsions = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of /data/bp2/convulsions = 'yes'"
    )
    rupture = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of /data/bp2/rupture = 'yes'"
    )
    anc_abnormalities = models.PositiveSmallIntegerField(
        null=True,
        help_text="Last value of anc_details/anc_abnormalities = 'yes'"
    )
    valid_visits = models.PositiveSmallIntegerField(
        help_text="number of qualified visits for the incentive report",
        default=0
    )
    play_birth_preparedness_vid = models.PositiveSmallIntegerField(
        null=True,
        help_text="Case has ever been counseled about birth preparedness with a video"
    )
    play_family_planning_vid = models.PositiveSmallIntegerField(
        null=True,
        help_text="Case has ever been counseled about family planning with a video"
    )
    counsel_preparation = models.PositiveSmallIntegerField(
        null=True,
        help_text="Has ever had /data/bp2/counsel_preparation = 'yes'"
    )
    conceive = models.PositiveSmallIntegerField(
        null=True,
        help_text="Has ever had /data/conceive = 'yes'"
    )
    counsel_accessible_ppfp = models.PositiveSmallIntegerField(
        null=True,
        help_text="Has ever had /data/family_planning_group/counsel_accessible_ppfp='yes'"
    )
    ifa_last_seven_days = models.PositiveSmallIntegerField(
        null=True,
        help_text="Number of ifa taken in last seven days"
    )
    using_ifa = models.PositiveSmallIntegerField(
        null=True,
        help_text="Has ever had /data/bp1/using_ifa='yes'"
    )

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_CCS_RECORD_BP_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = BirthPreparednessFormsAggregationHelper
    _agg_atomic = False

    @classmethod
    def compare_with_old_data(cls, state_id, month):
        helper = BirthPreparednessFormsAggregationHelper(state_id, month)
        query, params = helper.compare_with_old_data_query()

        with get_cursor(cls) as cursor:
            cursor.execute(query, params)
            rows = fetchall_as_namedtuple(cursor)
            return [row.case_id for row in rows]


class AggregateCcsRecordDeliveryForms(models.Model, AggregateMixin):
    """Aggregated data for ccs_record cases based on
    Delivery forms

    A child table exists for each state_id and month.

    A row exists for every ccs_record case that has had a Delivery Form
    submitted against it this month.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)

    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )
    breastfed_at_birth = models.PositiveSmallIntegerField(
        null=True,
        help_text="whether any child was breastfed at birth"
    )
    valid_visits = models.PositiveSmallIntegerField(
        help_text="number of qualified visits for the incentive report",
        default=0
    )
    where_born = models.PositiveSmallIntegerField(
        null=True,
        help_text="Where the child is born"
    )

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_CCS_RECORD_DELIVERY_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = DeliveryFormsAggregationHelper
    _agg_atomic = False


class AggregateInactiveAWW(models.Model, AggregateMixin):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    first_submission = models.DateField(blank=True, null=True)
    last_submission = models.DateField(blank=True, null=True)

    objects = CitusComparisonManager()

    @property
    def days_since_start(self):
        if self.first_submission:
            delta = date.today() - self.first_submission
            return delta.days
        return 'N/A'

    @property
    def days_inactive(self):
        if self.last_submission:
            delta = date.today() - self.last_submission
            return delta.days
        return 'N/A'

    class Meta(object):
        app_label = 'icds_reports'

    _agg_helper_cls = InactiveAwwsAggregationHelper
    _agg_atomic = False


class AggregateChildHealthDailyFeedingForms(models.Model, AggregateMixin):
    """Aggregated data for child_health cases based on
    Daily Feeding forms

    A child table exists for each state_id and month.

    A row exists for every child_health case that has had a daily feeding form
    submitted against it this month.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
    case_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )
    sum_attended_child_ids = models.PositiveSmallIntegerField(
        null=True,
        help_text="Number of days the child has attended this month"
    )
    lunch_count = models.PositiveSmallIntegerField(
        null=True,
        help_text="Number of days the child had the lunch"
    )

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_DAILY_FEEDING_TABLE
        unique_together = ('supervisor_id', 'case_id', 'month')  # pkey

    _agg_helper_cls = DailyFeedingFormsChildHealthAggregationHelper
    _agg_atomic = False


class AggregateAwcInfrastructureForms(models.Model, AggregateMixin):
    """Aggregated data for AWC locations based on infrastructure forms

    A child table exists for each state_id and month.

    Each of these columns represent the last non-null value from forms
    completed in the past six months unless otherwise noted.
    """

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # not the real pkey - see unique_together
    awc_id = models.CharField(max_length=40, primary_key=True)

    latest_time_end_processed = models.DateTimeField(
        help_text="The latest form.meta.timeEnd that has been processed for this case"
    )

    awc_building = models.PositiveSmallIntegerField(null=True)
    source_drinking_water = models.PositiveSmallIntegerField(null=True)
    toilet_functional = models.PositiveSmallIntegerField(null=True)
    electricity_awc = models.PositiveSmallIntegerField(null=True)
    adequate_space_pse = models.PositiveSmallIntegerField(null=True)

    adult_scale_available = models.PositiveSmallIntegerField(null=True)
    baby_scale_available = models.PositiveSmallIntegerField(null=True)
    flat_scale_available = models.PositiveSmallIntegerField(null=True)

    adult_scale_usable = models.PositiveSmallIntegerField(null=True)
    baby_scale_usable = models.PositiveSmallIntegerField(null=True)
    cooking_utensils_usable = models.PositiveSmallIntegerField(null=True)
    infantometer_usable = models.PositiveSmallIntegerField(null=True)
    medicine_kits_usable = models.PositiveSmallIntegerField(null=True)
    stadiometer_usable = models.PositiveSmallIntegerField(null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AGG_INFRASTRUCTURE_TABLE
        unique_together = ('supervisor_id', 'awc_id', 'month')  # pkey

    _agg_helper_cls = AwcInfrastructureAggregationHelper
    _agg_atomic = False


class AWWIncentiveReport(models.Model, AggregateMixin):
    """Monthly updated table that holds metrics for the incentive report"""

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    district_id = models.TextField(blank=True, null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # primary key as it's unique for every partition
    awc_id = models.CharField(max_length=40, primary_key=True)
    block_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    state_name = models.TextField(null=True)
    district_name = models.TextField(null=True)
    block_name = models.TextField(null=True)
    supervisor_name = models.TextField(null=True)
    awc_name = models.TextField(null=True)
    aww_name = models.TextField(null=True)
    contact_phone_number = models.TextField(null=True)
    wer_weighed = models.SmallIntegerField(null=True)
    wer_eligible = models.SmallIntegerField(null=True)
    awc_num_open = models.SmallIntegerField(null=True)
    valid_visits = models.SmallIntegerField(null=True)
    expected_visits = models.DecimalField(null=True, max_digits=64, decimal_places=2)
    visit_denominator = models.SmallIntegerField(null=True)
    incentive_eligible = models.NullBooleanField(null=True)
    awh_eligible = models.NullBooleanField(null=True)
    is_launched = models.NullBooleanField(null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        db_table = AWW_INCENTIVE_TABLE

    _agg_helper_cls = AwwIncentiveAggregationHelper
    _agg_atomic = False
