from __future__ import absolute_import, unicode_literals

import tempfile

from corehq.apps.locations.models import SQLLocation

from custom.icds_reports.models import CcsRecordMonthly, ChildHealthMonthly, AggAwc

class MBTHelper(object):

    def __init__(self, state_id, month):
        self.state_id = state_id
        self.month = month

    @property
    def columns(self):
        raise NotImplementedError
    
    @property
    def base_tablename(self):
        return self.base_class._meta.db_table

    @property
    def state_name(self):
        state = SQLLocation.objects.get(location_id=self.state_id)
        return state.name

    @property
    def output_file(self):
        temp_dir = tempfile.gettempdir()
        return '{}/{}_{}_{}.csv'.format(temp_dir, self.base_tablename, self.state_name, self.month)
    @property
    def location_columns(self):
        return ('awc.state_name', 'awc.district_name', 'awc.block_name', 'awc.awc_name', 'awc.awc_site_code')
    
    def query(self):
        return  """
        COPY (SELECT {columns} FROM {table} t LEFT JOIN awc_location awc on t.awc_id=awc.doc_id WHERE awc.state_id='{state_id}' AND t.month='{month}') TO '{output}' WITH CSV HEADER;
        """.format(
            columns=','.join(self.columns + self.location_columns),
            table=self.base_tablename,
            state_id=self.state_id,
            month=self.month,
            output=self.output_file
        )


class CcsMbtHelper(MBTHelper):
    base_class = CcsRecordMonthly

    @property
    def columns(self):
        return ('awc_id',
                'case_id',
                'month',
                'age_in_months',
                'ccs_status',
                'open_in_month',
                'alive_in_month',
                'trimester',
                'num_rations_distributed',
                'thr_eligible',
                'tetanus_complete',
                'delivered_in_month',
                'anc1_received_at_delivery',
                'anc2_received_at_delivery',
                'anc3_received_at_delivery',
                'anc4_received_at_delivery',
                'registration_trimester_at_delivery',
                'using_ifa',
                'ifa_consumed_last_seven_days',
                'anemic_severe',
                'anemic_moderate',
                'anemic_normal',
                'anemic_unknown',
                'extra_meal',
                'resting_during_pregnancy',
                'bp_visited_in_month',
                'pnc_visited_in_month',
                'trimester_2',
                'trimester_3',
                'counsel_immediate_bf',
                'counsel_bp_vid',
                'counsel_preparation',
                'counsel_fp_vid',
                'counsel_immediate_conception',
                'counsel_accessible_postpartum_fp',
                'bp1_complete',
                'bp2_complete',
                'bp3_complete',
                'pnc_complete',
                'postnatal',
                'has_aadhar_id',
                'counsel_fp_methods',
                'pregnant',
                'pregnant_all',
                'lactating',
                'lactating_all',
                'institutional_delivery_in_month',
                'add',
                'anc_in_month',
                'caste',
                'disabled',
                'minority',
                'resident',
                'anc_weight',
                'anc_blood_pressure',
                'bp_sys',
                'bp_dia',
                'anc_hemoglobin',
                'bleeding',
                'swelling',
                'blurred_vision',
                'convulsions',
                'rupture',
                'anemia',
                'eating_extra',
                'resting',
                'immediate_breastfeeding',
                'edd',
                'delivery_nature',
                'is_ebf',
                'breastfed_at_birth',
                'anc_1',
                'anc_2',
                'anc_3',
                'anc_4',
                'tt_1',
                'tt_2',
                'valid_in_month',
                'mobile_number',
                'preg_order',
                'home_visit_date',
                'num_pnc_visits',
                'last_date_thr',
                'num_anc_complete',
                'opened_on',
                'valid_visits',
                'dob',
                'date_death')


class ChildHealthMbtHelper(MBTHelper):
    base_class = ChildHealthMonthly

    @property
    def columns(self):
        return ('awc_id',
                'case_id',
                'month',
                'age_in_months',
                'open_in_month',
                'alive_in_month',
                'wer_eligible',
                'nutrition_status_last_recorded',
                'current_month_nutrition_status',
                'nutrition_status_weighed',
                'num_rations_distributed',
                'pse_eligible',
                'pse_days_attended',
                'born_in_month',
                'low_birth_weight_born_in_month',
                'bf_at_birth_born_in_month',
                'ebf_eligible',
                'ebf_in_month',
                'ebf_not_breastfeeding_reason',
                'ebf_drinking_liquid',
                'ebf_eating',
                'ebf_no_bf_no_milk',
                'ebf_no_bf_pregnant_again',
                'ebf_no_bf_child_too_old',
                'ebf_no_bf_mother_sick',
                'cf_eligible',
                'cf_in_month',
                'cf_diet_diversity',
                'cf_diet_quantity',
                'cf_handwashing',
                'cf_demo',
                'fully_immunized_eligible',
                'fully_immunized_on_time',
                'fully_immunized_late',
                'counsel_ebf',
                'counsel_adequate_bf',
                'counsel_pediatric_ifa',
                'counsel_comp_feeding_vid',
                'counsel_increase_food_bf',
                'counsel_manage_breast_problems',
                'counsel_skin_to_skin',
                'counsel_immediate_breastfeeding',
                'recorded_weight',
                'recorded_height',
                'has_aadhar_id',
                'thr_eligible',
                'pnc_eligible',
                'cf_initiation_in_month',
                'cf_initiation_eligible',
                'height_measured_in_month',
                'current_month_stunting',
                'stunting_last_recorded',
                'wasting_last_recorded',
                'current_month_wasting',
                'valid_in_month',
                'valid_all_registered_in_month',
                'ebf_no_info_recorded',
                'dob',
                'sex',
                'age_tranche',
                'caste',
                'disabled',
                'minority',
                'resident',
                'immunization_in_month',
                'days_ration_given_child',
                'zscore_grading_hfa',
                'zscore_grading_hfa_recorded_in_month',
                'zscore_grading_wfh',
                'zscore_grading_wfh_recorded_in_month',
                'muac_grading',
                'ccs_record_case_id',
                'date_death')


class AwcMbtHelper(MBTHelper):
    base_class = AggAwc

    @property
    def columns(self):
        return ('t.state_id',
                't.district_id',
                't.block_id',
                't.supervisor_id',
                't.awc_id',
                'month',
                'num_awcs',
                'awc_days_open',
                'total_eligible_children',
                'total_attended_children',
                'pse_avg_attendance_percent',
                'pse_full',
                'pse_partial',
                'pse_non',
                'pse_score',
                'awc_days_provided_breakfast',
                'awc_days_provided_hotmeal',
                'awc_days_provided_thr',
                'awc_days_provided_pse',
                'awc_not_open_holiday',
                'awc_not_open_festival',
                'awc_not_open_no_help',
                'awc_not_open_department_work',
                'awc_not_open_other',
                'awc_num_open',
                'awc_not_open_no_data',
                'wer_weighed',
                'wer_eligible',
                'wer_score',
                'thr_eligible_child',
                'thr_rations_21_plus_distributed_child',
                'thr_eligible_ccs',
                'thr_rations_21_plus_distributed_ccs',
                'thr_score',
                'awc_score',
                'num_awc_rank_functional',
                'num_awc_rank_semi',
                'num_awc_rank_non',
                'cases_ccs_pregnant',
                'cases_ccs_lactating',
                'cases_child_health',
                'usage_num_pse',
                'usage_num_gmp',
                'usage_num_thr',
                'usage_num_home_visit',
                'usage_num_bp_tri1',
                'usage_num_bp_tri2',
                'usage_num_bp_tri3',
                'usage_num_pnc',
                'usage_num_ebf',
                'usage_num_cf',
                'usage_num_delivery',
                'usage_num_due_list_ccs',
                'usage_num_due_list_child_health',
                'usage_awc_num_active',
                'usage_time_pse',
                'usage_time_gmp',
                'usage_time_bp',
                'usage_time_pnc',
                'usage_time_ebf',
                'usage_time_cf',
                'usage_time_of_day_pse',
                'usage_time_of_day_home_visit',
                'vhnd_immunization',
                'vhnd_anc',
                'vhnd_gmp',
                'vhnd_num_pregnancy',
                'vhnd_num_lactating',
                'vhnd_num_mothers_6_12',
                'vhnd_num_mothers_12',
                'vhnd_num_fathers',
                'ls_supervision_visit',
                'ls_num_supervised',
                'ls_awc_location_long',
                'ls_awc_location_lat',
                'ls_awc_present',
                'ls_awc_open',
                'ls_awc_not_open_aww_not_available',
                'ls_awc_not_open_closed_early',
                'ls_awc_not_open_holiday',
                'ls_awc_not_open_unknown',
                'ls_awc_not_open_other',
                'infra_last_update_date',
                'infra_type_of_building',
                'infra_type_of_building_pucca',
                'infra_type_of_building_semi_pucca',
                'infra_type_of_building_kuccha',
                'infra_type_of_building_partial_covered_space',
                'infra_clean_water',
                'infra_functional_toilet',
                'infra_baby_weighing_scale',
                'infra_flat_weighing_scale',
                'infra_adult_weighing_scale',
                'infra_cooking_utensils',
                'infra_medicine_kits',
                'infra_adequate_space_pse',
                'cases_person_beneficiary',
                'cases_person_referred',
                'awc_days_pse_conducted',
                'num_awc_infra_last_update',
                'cases_person_has_aadhaar_v2',
                'cases_person_beneficiary_v2',
                'electricity_awc',
                'infantometer',
                'stadiometer',
                'num_anc_visits',
                'num_children_immunized',
                'usage_num_hh_reg',
                'usage_num_add_person',
                'usage_num_add_pregnancy',
                'is_launched',
                'training_phase',
                'trained_phase_1',
                'trained_phase_2',
                'trained_phase_3',
                'trained_phase_4',
                't.aggregation_level',
                'num_launched_states',
                'num_launched_districts',
                'num_launched_blocks',
                'num_launched_supervisors',
                'num_launched_awcs',
                'cases_household',
                'cases_person',
                'cases_person_all',
                'cases_person_has_aadhaar',
                'cases_ccs_pregnant_all',
                'cases_ccs_lactating_all',
                'cases_child_health_all',
                'cases_person_adolescent_girls_11_14',
                'cases_person_adolescent_girls_15_18',
                'cases_person_adolescent_girls_11_14_all',
                'cases_person_adolescent_girls_15_18_all',
                'infra_infant_weighing_scale')

    def query(self):
        return  """
        COPY (SELECT {columns} FROM {table} t LEFT JOIN awc_location awc on t.awc_id=awc.doc_id WHERE awc.state_id='{state_id}' AND t.month='{month}' and t.aggregation_level=5) TO '{output}' WITH CSV HEADER;
        """.format(
            columns=','.join(self.columns + self.location_columns),
            table=self.base_tablename,
            state_id=self.state_id,
            month=self.month,
            output=self.output_file
        )
