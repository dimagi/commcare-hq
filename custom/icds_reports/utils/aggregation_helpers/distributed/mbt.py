from __future__ import absolute_import, unicode_literals

from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.utils.aggregation_helpers import AggregationHelper


class MBTDistributedHelper(AggregationHelper):

    def __init__(self, state_id, month):
        self.state_id = state_id
        self.month = month

    @property
    def domain(self):
        # Currently its only possible for one domain to have access to the ICDS dashboard per env
        return DASHBOARD_DOMAIN

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
    def location_columns(self):
        return ('awc.state_name', 'awc.district_name', 'awc.block_name', 'awc.awc_name', 'awc.awc_site_code')

    def query(self):
        return """
        COPY (
            SELECT {columns} FROM {table} t LEFT JOIN awc_location awc on t.awc_id=awc.doc_id
                AND awc.supervisor_id=t.supervisor_id
            WHERE awc.state_id='{state_id}' AND t.month='{month}'
        ) TO STDOUT WITH CSV HEADER ENCODING 'UTF-8';
        """.format(
            columns=','.join(self.columns + self.location_columns),
            table=self.base_tablename,
            state_id=self.state_id,
            month=self.month
        )


class CcsMbtDistributedHelper(MBTDistributedHelper):
    helper_key = 'css-mbt'

    @property
    def base_class(self):
        from custom.icds_reports.models import CcsRecordMonthly
        return CcsRecordMonthly

    @property
    def columns(self):
        return ('t.awc_id',
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


class ChildHealthMbtDistributedHelper(MBTDistributedHelper):
    helper_key = 'child-health-mbt'

    @property
    def base_class(self):
        from custom.icds_reports.models import ChildHealthMonthly
        return ChildHealthMonthly

    @property
    def person_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-person_cases_v3')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def columns(self):
        return ('t.awc_id',
                't.case_id',
                't.month',
                't.age_in_months',
                't.open_in_month',
                't.alive_in_month',
                't.wer_eligible',
                't.nutrition_status_last_recorded',
                't.current_month_nutrition_status',
                't.nutrition_status_weighed',
                't.num_rations_distributed',
                't.pse_eligible',
                't.pse_days_attended',
                't.born_in_month',
                't.low_birth_weight_born_in_month',
                't.bf_at_birth_born_in_month',
                't.ebf_eligible',
                't.ebf_in_month',
                't.ebf_not_breastfeeding_reason',
                't.ebf_drinking_liquid',
                't.ebf_eating',
                't.ebf_no_bf_no_milk',
                't.ebf_no_bf_pregnant_again',
                't.ebf_no_bf_child_too_old',
                't.ebf_no_bf_mother_sick',
                't.cf_eligible',
                't.cf_in_month',
                't.cf_diet_diversity',
                't.cf_diet_quantity',
                't.cf_handwashing',
                't.cf_demo',
                't.fully_immunized_eligible',
                't.fully_immunized_on_time',
                't.fully_immunized_late',
                't.counsel_ebf',
                't.counsel_adequate_bf',
                't.counsel_pediatric_ifa',
                't.counsel_comp_feeding_vid',
                't.counsel_increase_food_bf',
                't.counsel_manage_breast_problems',
                't.counsel_skin_to_skin',
                't.counsel_immediate_breastfeeding',
                't.recorded_weight',
                't.recorded_height',
                't.has_aadhar_id',
                't.thr_eligible',
                't.pnc_eligible',
                't.cf_initiation_in_month',
                't.cf_initiation_eligible',
                't.height_measured_in_month',
                't.current_month_stunting',
                't.stunting_last_recorded',
                't.wasting_last_recorded',
                't.current_month_wasting',
                't.valid_in_month',
                't.valid_all_registered_in_month',
                't.ebf_no_info_recorded',
                't.dob',
                't.sex',
                't.age_tranche',
                't.caste',
                't.disabled',
                't.minority',
                't.resident',
                't.immunization_in_month',
                't.days_ration_given_child',
                't.zscore_grading_hfa',
                't.zscore_grading_hfa_recorded_in_month',
                't.zscore_grading_wfh',
                't.zscore_grading_wfh_recorded_in_month',
                't.muac_grading',
                'ccs.case_id as ccs_record_case_id',
                't.date_death')

    def query(self):
        return """
        COPY (
            SELECT {columns} FROM {table} t
            LEFT JOIN awc_location awc on t.awc_id=awc.doc_id and awc.supervisor_id=t.supervisor_id
            LEFT JOIN "{person_cases_ucr}" mother on mother.doc_id=t.mother_case_id
              AND awc.state_id = mother.state_id and mother.supervisor_id=t.supervisor_id
              AND lower(substring(mother.state_id, '.{{3}}$'::text)) = '{state_id_last_3}'
            LEFT JOIN "ccs_record_monthly" ccs on ccs.person_case_id=mother.doc_id AND ccs.add=t.dob
                AND (ccs.child_name is null OR ccs.child_name=t.person_name)
                AND ccs.month=t.month AND ccs.supervisor_id=t.supervisor_id
            WHERE awc.state_id='{state_id}' AND t.month='{month}'
        ) TO STDOUT WITH CSV HEADER ENCODING 'UTF-8';
        """.format(
            columns=','.join(self.columns + self.location_columns),
            table=self.base_tablename,
            state_id=self.state_id,
            month=self.month,
            person_cases_ucr=self.person_case_ucr_tablename,
            state_id_last_3=self.state_id[-3:]
        )


class AwcMbtDistributedHelper(MBTDistributedHelper):
    helper_key = 'awc-mbt'

    @property
    def base_class(self):
        from custom.icds_reports.models import AggAwc
        return AggAwc

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
        return """
        COPY (
            SELECT {columns} FROM {table} t LEFT JOIN "awc_location_local" awc on t.awc_id=awc.doc_id
            WHERE awc.state_id='{state_id}' AND t.month='{month}'
            AND t.aggregation_level=5
        ) TO STDOUT WITH CSV HEADER ENCODING 'UTF-8';
        """.format(
            columns=','.join(self.columns + self.location_columns),
            table=self.base_tablename,
            state_id=self.state_id,
            month=self.month
        )
