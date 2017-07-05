DROP VIEW IF EXISTS awc_location_months CASCADE;
CREATE VIEW awc_location_months AS
 SELECT
	awc_location.doc_id as awc_id,
    awc_location.awc_name,
	awc_location.awc_site_code,
    awc_location.supervisor_id,
	awc_location.supervisor_name,
	awc_location.supervisor_site_code,
	awc_location.block_id,
	awc_location.block_name,
	awc_location.block_site_code,
	awc_location.district_id,
	awc_location.district_name,
	awc_location.district_site_code,
	awc_location.state_id,
	awc_location.state_name,
	awc_location.state_site_code,
	awc_location.aggregation_level,
    months.start_date AS month,
	months.month_name AS month_display
  FROM awc_location awc_location
  CROSS JOIN "icds_months" months;

DROP VIEW IF EXISTS agg_awc_monthly CASCADE;
CREATE VIEW agg_awc_monthly AS
    SELECT
        "awc_location_months"."awc_id" AS "awc_id",
        "awc_location_months"."awc_name" AS "awc_name",
        "awc_location_months"."awc_site_code" AS "awc_site_code",
        "awc_location_months"."supervisor_id" AS "supervisor_id",
        "awc_location_months"."supervisor_name" AS "supervisor_name",
        "awc_location_months"."supervisor_site_code" AS "supervisor_site_code",
        "awc_location_months"."block_id" AS "block_id",
        "awc_location_months"."block_name" AS "block_name",
        "awc_location_months"."block_site_code" AS "block_site_code",
        "awc_location_months"."district_id" AS "district_id",
        "awc_location_months"."district_name" AS "district_name",
        "awc_location_months"."district_site_code" AS "district_site_code",
        "awc_location_months"."state_id" AS "state_id",
        "awc_location_months"."state_name" AS "state_name",
        "awc_location_months"."state_site_code" AS "state_site_code",
        "awc_location_months"."aggregation_level" AS "aggregation_level",
        "awc_location_months"."month" AS "month",
        "agg_awc"."is_launched" AS "is_launched",
        "agg_awc"."num_awcs" AS "num_awcs",
        "agg_awc"."num_launched_states" AS "num_awcs",
        "agg_awc"."num_launched_districts" AS "num_awcs",
        "agg_awc"."num_launched_blocks" AS "num_awcs",
        "agg_awc"."num_launched_supervisors" AS "num_awcs",
        "agg_awc"."num_launched_awcs" AS "num_awcs",
        "agg_awc"."awc_days_open" AS "awc_days_open",
        "agg_awc"."total_eligible_children" AS "total_eligible_children",
        "agg_awc"."total_attended_children" AS "total_attended_children",
        "agg_awc"."pse_avg_attendance_percent" AS "pse_avg_attendance_percent",
        "agg_awc"."pse_full" AS "pse_full",
        "agg_awc"."pse_partial" AS "pse_partial",
        "agg_awc"."pse_non" AS "pse_non",
        "agg_awc"."pse_score" AS "pse_score",
        "agg_awc"."awc_days_provided_breakfast" AS "awc_days_provided_breakfast",
        "agg_awc"."awc_days_provided_hotmeal" AS "awc_days_provided_hotmeal",
        "agg_awc"."awc_days_provided_thr" AS "awc_days_provided_thr",
        "agg_awc"."awc_days_provided_pse" AS "awc_days_provided_pse",
        "agg_awc"."awc_not_open_holiday" AS "awc_not_open_holiday",
        "agg_awc"."awc_not_open_festival" AS "awc_not_open_festival",
        "agg_awc"."awc_not_open_no_help" AS "awc_not_open_no_help",
        "agg_awc"."awc_not_open_department_work" AS "awc_not_open_department_work",
        "agg_awc"."awc_not_open_other" AS "awc_not_open_other",
        "agg_awc"."awc_num_open" AS "awc_num_open",
        "agg_awc"."awc_not_open_no_data" AS "awc_not_open_no_data",
        "agg_awc"."wer_weighed" AS "wer_weighed",
        "agg_awc"."wer_eligible" AS "wer_eligible",
        "agg_awc"."wer_score" AS "wer_score",
        "agg_awc"."thr_eligible_child" AS "thr_eligible_child",
        "agg_awc"."thr_rations_21_plus_distributed_child" AS "thr_rations_21_plus_distributed_child",
        "agg_awc"."thr_eligible_ccs" AS "thr_eligible_ccs",
        "agg_awc"."thr_rations_21_plus_distributed_ccs" AS "thr_rations_21_plus_distributed_ccs",
        "agg_awc"."thr_score" AS "thr_score",
        "agg_awc"."awc_score" AS "awc_score",
        "agg_awc"."num_awc_rank_functional" AS "num_awc_rank_functional",
        "agg_awc"."num_awc_rank_semi" AS "num_awc_rank_semi",
        "agg_awc"."num_awc_rank_non" AS "num_awc_rank_non",
        COALESCE("agg_awc"."cases_household", 0) AS "cases_household",
        COALESCE("agg_awc"."cases_person", 0) AS "cases_person",
        COALESCE("agg_awc"."cases_person_all", 0) AS "cases_person_all",
        COALESCE("agg_awc"."cases_person_has_aadhaar", 0) AS "cases_person_has_aadhaar",
        COALESCE("agg_awc"."cases_person_adolescent_girls_11_14", 0) AS "cases_person_adolescent_girls_11_14",
        COALESCE("agg_awc"."cases_person_adolescent_girls_15_18", 0) AS "cases_person_adolescent_girls_15_18",
        COALESCE("agg_awc"."cases_person_adolescent_girls_11_14_all", 0) AS "cases_person_adolescent_girls_11_14_all",
        COALESCE("agg_awc"."cases_person_adolescent_girls_15_18_all", 0) AS "cases_person_adolescent_girls_15_18_all",
        COALESCE("agg_awc"."cases_ccs_pregnant", 0) AS "cases_ccs_pregnant",
        COALESCE("agg_awc"."cases_ccs_lactating", 0) AS "cases_ccs_lactating",
        COALESCE("agg_awc"."cases_child_health", 0) AS "cases_child_health",
        COALESCE("agg_awc"."cases_ccs_pregnant_all", 0) AS "cases_ccs_pregnant_all",
        COALESCE("agg_awc"."cases_ccs_lactating_all", 0) AS "cases_ccs_lactating_all",
        COALESCE("agg_awc"."cases_child_health_all", 0) AS "cases_child_health_all",
        COALESCE("agg_awc"."usage_num_pse", 0) AS "usage_num_pse",
        COALESCE("agg_awc"."usage_num_gmp", 0) AS "usage_num_gmp",
        COALESCE("agg_awc"."usage_num_thr", 0) AS "usage_num_thr",
        COALESCE("agg_awc"."usage_num_home_visit", 0) AS "usage_num_home_visit",
        COALESCE("agg_awc"."usage_num_bp_tri1", 0) AS "usage_num_bp_tri1",
        COALESCE("agg_awc"."usage_num_bp_tri2", 0) AS "usage_num_bp_tri2",
        COALESCE("agg_awc"."usage_num_bp_tri3", 0) AS "usage_num_bp_tri3",
        COALESCE("agg_awc"."usage_num_pnc", 0) AS "usage_num_pnc",
        COALESCE("agg_awc"."usage_num_ebf", 0) AS "usage_num_ebf",
        COALESCE("agg_awc"."usage_num_cf", 0) AS "usage_num_cf",
        COALESCE("agg_awc"."usage_num_delivery", 0) AS "usage_num_delivery",
        COALESCE("agg_awc"."usage_num_due_list_ccs", 0) AS "usage_num_due_list_ccs",
        COALESCE("agg_awc"."usage_num_due_list_child_health", 0) AS "usage_num_due_list_child_health",
        COALESCE("agg_awc"."usage_awc_num_active", 0) AS "usage_awc_num_active",
        "agg_awc"."usage_time_pse" AS "usage_time_pse",
        "agg_awc"."usage_time_gmp" AS "usage_time_gmp",
        "agg_awc"."usage_time_bp" AS "usage_time_bp",
        "agg_awc"."usage_time_pnc" AS "usage_time_pnc",
        "agg_awc"."usage_time_ebf" AS "usage_time_ebf",
        "agg_awc"."usage_time_cf" AS "usage_time_cf",
        "agg_awc"."usage_time_of_day_pse" AS "usage_time_of_day_pse",
        "agg_awc"."usage_time_of_day_home_visit" AS "usage_time_of_day_home_visit",
        "agg_awc"."vhnd_immunization" AS "vhnd_immunization",
        "agg_awc"."vhnd_anc" AS "vhnd_anc",
        "agg_awc"."vhnd_gmp" AS "vhnd_gmp",
        "agg_awc"."vhnd_num_pregnancy" AS "vhnd_num_pregnancy",
        "agg_awc"."vhnd_num_lactating" AS "vhnd_num_lactating",
        "agg_awc"."vhnd_num_mothers_6_12" AS "vhnd_num_mothers_6_12",
        "agg_awc"."vhnd_num_mothers_12" AS "vhnd_num_mothers_12",
        "agg_awc"."vhnd_num_fathers" AS "vhnd_num_fathers",
        COALESCE("agg_awc"."ls_supervision_visit", 0) AS "ls_supervision_visit",
        "agg_awc"."ls_num_supervised" AS "ls_num_supervised",
        "agg_awc"."ls_awc_location_long" AS "ls_awc_location_long",
        "agg_awc"."ls_awc_location_lat" AS "ls_awc_location_lat",
        "agg_awc"."ls_awc_present" AS "ls_awc_present",
        "agg_awc"."ls_awc_open" AS "ls_awc_open",
        "agg_awc"."ls_awc_not_open_aww_not_available" AS "ls_awc_not_open_aww_not_available",
        "agg_awc"."ls_awc_not_open_closed_early" AS "ls_awc_not_open_closed_early",
        "agg_awc"."ls_awc_not_open_holiday" AS "ls_awc_not_open_holiday",
        "agg_awc"."ls_awc_not_open_unknown" AS "ls_awc_not_open_unknown",
        "agg_awc"."ls_awc_not_open_other" AS "ls_awc_not_open_other",
        "agg_awc"."infra_last_update_date" AS "infra_last_update_date",
        "agg_awc"."infra_type_of_building" AS "infra_type_of_building",
        "agg_awc"."infra_type_of_building_pucca" AS "infra_type_of_building_pucca",
        "agg_awc"."infra_type_of_building_semi_pucca" AS "infra_type_of_building_semi_pucca",
        "agg_awc"."infra_type_of_building_kuccha" AS "infra_type_of_building_kuccha",
        "agg_awc"."infra_type_of_building_partial_covered_space" AS "infra_type_of_building_partial_covered_space",
        "agg_awc"."infra_clean_water" AS "infra_clean_water",
        "agg_awc"."infra_functional_toilet" AS "infra_functional_toilet",
        "agg_awc"."infra_baby_weighing_scale" AS "infra_baby_weighing_scale",
        "agg_awc"."infra_flat_weighing_scale" AS "infra_flat_weighing_scale",
        "agg_awc"."infra_adult_weighing_scale" AS "infra_adult_weighing_scale",
        "agg_awc"."infra_cooking_utensils" AS "infra_cooking_utensils",
        "agg_awc"."infra_medicine_kits" AS "infra_medicine_kits",
        "agg_awc"."infra_adequate_space_pse" AS "infra_adequate_space_pse",
        COALESCE("agg_awc"."usage_num_hh_reg", 0) AS "usage_num_hh_reg",
        COALESCE("agg_awc"."usage_num_add_person", 0) AS "usage_num_add_person",
        COALESCE("agg_awc"."usage_num_add_pregnancy", 0) AS "usage_num_add_pregnancy",
        "agg_awc"."training_phase" AS "training_phase",
        COALESCE("agg_awc"."trained_phase_1", 0) AS "trained_phase_1",
        COALESCE("agg_awc"."trained_phase_2", 0) AS "trained_phase_2",
        COALESCE("agg_awc"."trained_phase_3", 0) AS "trained_phase_3",
        COALESCE("agg_awc"."trained_phase_4", 0) AS "trained_phase_4"
    FROM "public"."awc_location_months" "awc_location_months"
    LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
    );

DROP VIEW IF EXISTS agg_ccs_record_monthly CASCADE;
CREATE VIEW agg_ccs_record_monthly AS
    SELECT
        "awc_location_months"."awc_id" AS "awc_id",
        "awc_location_months"."awc_name" AS "awc_name",
        "awc_location_months"."awc_site_code" AS "awc_site_code",
        "awc_location_months"."supervisor_id" AS "supervisor_id",
        "awc_location_months"."supervisor_name" AS "supervisor_name",
        "awc_location_months"."supervisor_site_code" AS "supervisor_site_code",
        "awc_location_months"."block_id" AS "block_id",
        "awc_location_months"."block_name" AS "block_name",
        "awc_location_months"."block_site_code" AS "block_site_code",
        "awc_location_months"."district_id" AS "district_id",
        "awc_location_months"."district_name" AS "district_name",
        "awc_location_months"."district_site_code" AS "district_site_code",
        "awc_location_months"."state_id" AS "state_id",
        "awc_location_months"."state_name" AS "state_name",
        "awc_location_months"."state_site_code" AS "state_site_code",
        "awc_location_months"."aggregation_level" AS "aggregation_level",
        "awc_location_months"."month" AS "month",
        "agg_ccs_record"."ccs_status" AS "ccs_status",
        "agg_ccs_record"."trimester" AS "trimester",
        "agg_ccs_record"."caste" AS "caste",
        "agg_ccs_record"."disabled" AS "disabled",
        "agg_ccs_record"."minority" AS "minority",
        "agg_ccs_record"."resident" AS "resident",
        COALESCE("agg_ccs_record"."valid_in_month", 0) AS "valid_in_month",
        COALESCE("agg_ccs_record"."valid_all_registered_in_month", 0) AS "valid_all_registered_in_month",
        COALESCE("agg_ccs_record"."lactating", 0) AS "lactating",
        COALESCE("agg_ccs_record"."pregnant", 0) AS "pregnant",
        COALESCE("agg_ccs_record"."lactating_all", 0) AS "lactating_all",
        COALESCE("agg_ccs_record"."pregnant_all", 0) AS "pregnant_all",
        COALESCE("agg_ccs_record"."thr_eligible", 0) AS "thr_eligible",
        COALESCE("agg_ccs_record"."rations_21_plus_distributed", 0) AS "rations_21_plus_distributed",
        COALESCE("agg_ccs_record"."tetanus_complete", 0) AS "tetanus_complete",
        COALESCE("agg_ccs_record"."delivered_in_month", 0) AS "delivered_in_month",
        COALESCE("agg_ccs_record"."anc1_received_at_delivery", 0) AS "anc1_received_at_delivery",
        COALESCE("agg_ccs_record"."anc2_received_at_delivery", 0) AS "anc2_received_at_delivery",
        COALESCE("agg_ccs_record"."anc3_received_at_delivery", 0) AS "anc3_received_at_delivery",
        COALESCE("agg_ccs_record"."anc4_received_at_delivery", 0) AS "anc4_received_at_delivery",
        COALESCE("agg_ccs_record"."registration_trimester_at_delivery", 0) AS "registration_trimester_at_delivery",
        COALESCE("agg_ccs_record"."institutional_delivery_in_month", 0) AS "institutional_delivery_in_month",
        COALESCE("agg_ccs_record"."using_ifa", 0) AS "using_ifa",
        COALESCE("agg_ccs_record"."ifa_consumed_last_seven_days", 0) AS "ifa_consumed_last_seven_days",
        COALESCE("agg_ccs_record"."anemic_normal", 0) AS "anemic_normal",
        COALESCE("agg_ccs_record"."anemic_moderate", 0) AS "anemic_moderate",
        COALESCE("agg_ccs_record"."anemic_severe", 0) AS "anemic_severe",
        COALESCE("agg_ccs_record"."anemic_unknown", 0) AS "anemic_unknown",
        COALESCE("agg_ccs_record"."extra_meal", 0) AS "extra_meal",
        COALESCE("agg_ccs_record"."resting_during_pregnancy", 0) AS "resting_during_pregnancy",
        COALESCE("agg_ccs_record"."bp1_complete", 0) AS "bp1_complete",
        COALESCE("agg_ccs_record"."bp2_complete", 0) AS "bp2_complete",
        COALESCE("agg_ccs_record"."bp3_complete", 0) AS "bp3_complete",
        COALESCE("agg_ccs_record"."pnc_complete", 0) AS "pnc_complete",
        COALESCE("agg_ccs_record"."trimester_2", 0) AS "trimester_2",
        COALESCE("agg_ccs_record"."trimester_3", 0) AS "trimester_3",
        COALESCE("agg_ccs_record"."postnatal", 0) AS "postnatal",
        COALESCE("agg_ccs_record"."counsel_bp_vid", 0) AS "counsel_bp_vid",
        COALESCE("agg_ccs_record"."counsel_preparation", 0) AS "counsel_preparation",
        COALESCE("agg_ccs_record"."counsel_immediate_bf", 0) AS "counsel_immediate_bf",
        COALESCE("agg_ccs_record"."counsel_fp_vid", 0) AS "counsel_fp_vid",
        COALESCE("agg_ccs_record"."counsel_immediate_conception", 0) AS "counsel_immediate_conception",
        COALESCE("agg_ccs_record"."counsel_accessible_postpartum_fp", 0) AS "counsel_accessible_postpartum_fp"
    FROM "public"."awc_location_months" "awc_location_months"
    CROSS JOIN "public"."ccs_record_categories" "ccs_record_categories"
    LEFT JOIN "public"."agg_ccs_record" "agg_ccs_record" ON (
        ("awc_location_months"."month" = "agg_ccs_record"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_ccs_record"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_ccs_record"."state_id") AND
        ("awc_location_months"."district_id" = "agg_ccs_record"."district_id") AND
        ("awc_location_months"."block_id" = "agg_ccs_record"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_ccs_record"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_ccs_record"."awc_id")
    );

DROP VIEW IF EXISTS agg_child_health_monthly CASCADE;
CREATE VIEW agg_child_health_monthly AS
    SELECT
        "awc_location_months"."awc_id" AS "awc_id",
        "awc_location_months"."awc_name" AS "awc_name",
        "awc_location_months"."awc_site_code" AS "awc_site_code",
        "awc_location_months"."supervisor_id" AS "supervisor_id",
        "awc_location_months"."supervisor_name" AS "supervisor_name",
        "awc_location_months"."supervisor_site_code" AS "supervisor_site_code",
        "awc_location_months"."block_id" AS "block_id",
        "awc_location_months"."block_name" AS "block_name",
        "awc_location_months"."block_site_code" AS "block_site_code",
        "awc_location_months"."district_id" AS "district_id",
        "awc_location_months"."district_name" AS "district_name",
        "awc_location_months"."district_site_code" AS "district_site_code",
        "awc_location_months"."state_id" AS "state_id",
        "awc_location_months"."state_name" AS "state_name",
        "awc_location_months"."state_site_code" AS "state_site_code",
        "awc_location_months"."aggregation_level" AS "aggregation_level",
        "awc_location_months"."month" AS "month",
        "awc_location_months"."month_display" AS "month_display",
        "agg_child_health"."gender" AS "gender",
        "agg_child_health"."age_tranche" AS "age_tranche",
        "agg_child_health"."caste" AS "caste",
        "agg_child_health"."disabled" AS "disabled",
        "agg_child_health"."minority" AS "minority",
        "agg_child_health"."resident" AS "resident",
        COALESCE("agg_child_health"."valid_in_month", 0) AS "valid_in_month",
        COALESCE("agg_child_health"."valid_all_registered_in_month", 0) AS "valid_all_registered_in_month",
        COALESCE("agg_child_health"."nutrition_status_weighed", 0) AS "nutrition_status_weighed",
        COALESCE("agg_child_health"."nutrition_status_unweighed", 0) AS "nutrition_status_unweighed",
        COALESCE("agg_child_health"."nutrition_status_normal", 0) AS "nutrition_status_normal",
        COALESCE("agg_child_health"."nutrition_status_moderately_underweight", 0) AS "nutrition_status_moderately_underweight",
        COALESCE("agg_child_health"."nutrition_status_severely_underweight", 0) AS "nutrition_status_severely_underweight",
        COALESCE("agg_child_health"."wer_eligible", 0) AS "wer_eligible",
        COALESCE("agg_child_health"."height_measured_in_month", 0) AS "height_measured_in_month",
        COALESCE("agg_child_health"."height_eligible", 0) AS "height_eligible",
        COALESCE("agg_child_health"."wasting_moderate", 0) AS "wasting_moderate",
        COALESCE("agg_child_health"."wasting_severe", 0) AS "wasting_severe",
        COALESCE("agg_child_health"."wasting_normal", 0) AS "wasting_normal",
        COALESCE("agg_child_health"."wasting_moderate", 0) AS "stunting_moderate",
        COALESCE("agg_child_health"."wasting_severe", 0) AS "stunting_severe",
        COALESCE("agg_child_health"."stunting_normal", 0) AS "stunting_normal",
        COALESCE("agg_child_health"."pnc_eligible", 0) AS "pnc_eligible",
        COALESCE("agg_child_health"."thr_eligible", 0) AS "thr_eligible",
        COALESCE("agg_child_health"."rations_21_plus_distributed", 0) AS "rations_21_plus_distributed",
        COALESCE("agg_child_health"."pse_eligible", 0) AS "pse_eligible",
        COALESCE("agg_child_health"."pse_attended_16_days", 0) AS "pse_attended_16_days",
        COALESCE("agg_child_health"."born_in_month", 0) AS "born_in_month",
        COALESCE("agg_child_health"."low_birth_weight_in_month", 0) AS "low_birth_weight_in_month",
        COALESCE("agg_child_health"."bf_at_birth", 0) AS "bf_at_birth",
        COALESCE("agg_child_health"."ebf_eligible", 0) AS "ebf_eligible",
        COALESCE("agg_child_health"."ebf_in_month", 0) AS "ebf_in_month",
        COALESCE("agg_child_health"."cf_initiation_in_month", 0) AS "cf_initiation_in_month",
        COALESCE("agg_child_health"."cf_initiation_eligible", 0) AS "cf_initiation_eligible",
        COALESCE("agg_child_health"."cf_eligible", 0) AS "cf_eligible",
        COALESCE("agg_child_health"."cf_in_month", 0) AS "cf_in_month",
        COALESCE("agg_child_health"."cf_diet_diversity", 0) AS "cf_diet_diversity",
        COALESCE("agg_child_health"."cf_diet_quantity", 0) AS "cf_diet_quantity",
        COALESCE("agg_child_health"."cf_demo", 0) AS "cf_demo",
        COALESCE("agg_child_health"."cf_handwashing", 0) AS "cf_handwashing",
        COALESCE("agg_child_health"."counsel_increase_food_bf", 0) AS "counsel_increase_food_bf",
        COALESCE("agg_child_health"."counsel_manage_breast_problems", 0) AS "counsel_manage_breast_problems",
        COALESCE("agg_child_health"."counsel_ebf", 0) AS "counsel_ebf",
        COALESCE("agg_child_health"."counsel_adequate_bf", 0) AS "counsel_adequate_bf",
        COALESCE("agg_child_health"."counsel_pediatric_ifa", 0) AS "counsel_pediatric_ifa",
        COALESCE("agg_child_health"."counsel_play_cf_video", 0) AS "counsel_play_cf_video",
        COALESCE("agg_child_health"."fully_immunized_eligible", 0) AS "fully_immunized_eligible",
        COALESCE("agg_child_health"."fully_immunized_on_time", 0) AS "fully_immunized_on_time",
        COALESCE("agg_child_health"."fully_immunized_late", 0) AS "fully_immunized_late"
    FROM "public"."awc_location_months" "awc_location_months"
    LEFT JOIN "public"."agg_child_health" "agg_child_health" ON (
        ("awc_location_months"."month" = "agg_child_health"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_child_health"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_child_health"."state_id") AND
        ("awc_location_months"."district_id" = "agg_child_health"."district_id") AND
        ("awc_location_months"."block_id" = "agg_child_health"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_child_health"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_child_health"."awc_id")
    );

DROP VIEW IF EXISTS agg_thr_monthly CASCADE;
CREATE VIEW agg_thr_monthly AS
    SELECT
        "awc_location_months"."awc_id" AS "awc_id",
        "awc_location_months"."awc_name" AS "awc_name",
        "awc_location_months"."awc_site_code" AS "awc_site_code",
        "awc_location_months"."supervisor_id" AS "supervisor_id",
        "awc_location_months"."supervisor_name" AS "supervisor_name",
        "awc_location_months"."supervisor_site_code" AS "supervisor_site_code",
        "awc_location_months"."block_id" AS "block_id",
        "awc_location_months"."block_name" AS "block_name",
        "awc_location_months"."block_site_code" AS "block_site_code",
        "awc_location_months"."district_id" AS "district_id",
        "awc_location_months"."district_name" AS "district_name",
        "awc_location_months"."district_site_code" AS "district_site_code",
        "awc_location_months"."state_id" AS "state_id",
        "awc_location_months"."state_name" AS "state_name",
        "awc_location_months"."state_site_code" AS "state_site_code",
        "awc_location_months"."aggregation_level" AS "aggregation_level",
        "awc_location_months"."month" AS "month",
        "thr_categories"."beneficiary_type" AS "beneficiary_type",
        "thr_categories"."caste" AS "caste",
        "thr_categories"."disabled" AS "disabled",
        "thr_categories"."minority" AS "minority",
        "thr_categories"."resident" AS "resident",
        COALESCE("agg_thr_data"."thr_eligible", 0) AS "thr_eligible",
        COALESCE("agg_thr_data"."rations_21_plus_distributed", 0) AS "rations_21_plus_distributed"
    FROM "public"."awc_location_months" "awc_location_months"
    CROSS JOIN "public"."thr_categories" "thr_categories"
    LEFT JOIN "public"."agg_thr_data" "agg_thr_data" ON (
        ("awc_location_months"."month" = "agg_thr_data"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_thr_data"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_thr_data"."state_id") AND
        ("awc_location_months"."district_id" = "agg_thr_data"."district_id") AND
        ("awc_location_months"."block_id" = "agg_thr_data"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_thr_data"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_thr_data"."awc_id") AND
        ("thr_categories"."beneficiary_type" = "agg_thr_data"."beneficiary_type") AND
        ("thr_categories"."caste" = "agg_thr_data"."caste") AND
        ("thr_categories"."disabled" = "agg_thr_data"."disabled") AND
        ("thr_categories"."minority" = "agg_thr_data"."minority") AND
        ("thr_categories"."resident" = "agg_thr_data"."resident")
    );

DROP VIEW IF EXISTS daily_attendance_view CASCADE;
CREATE VIEW daily_attendance_view AS
    SELECT "awc_location_months"."awc_id" AS "awc_id",
        "awc_location_months"."awc_name" AS "awc_name",
        "awc_location_months"."awc_site_code" AS "awc_site_code",
        "awc_location_months"."supervisor_id" AS "supervisor_id",
        "awc_location_months"."supervisor_name" AS "supervisor_name",
        "awc_location_months"."supervisor_site_code" AS "supervisor_site_code",
        "awc_location_months"."block_id" AS "block_id",
        "awc_location_months"."block_name" AS "block_name",
        "awc_location_months"."block_site_code" AS "block_site_code",
        "awc_location_months"."district_id" AS "district_id",
        "awc_location_months"."district_name" AS "district_name",
        "awc_location_months"."district_site_code" AS "district_site_code",
        "awc_location_months"."state_id" AS "state_id",
        "awc_location_months"."state_name" AS "state_name",
        "awc_location_months"."state_site_code" AS "state_site_code",
        "awc_location_months"."aggregation_level" AS "aggregation_level",
        "awc_location_months"."month" AS "month",
        "daily_attendance"."doc_id" AS "doc_id",
        "daily_attendance"."pse_date" AS "pse_date",
        "daily_attendance"."awc_open_count" AS "awc_open_count",
        "daily_attendance"."count" AS "count",
        "daily_attendance"."eligible_children" AS "eligible_children",
        "daily_attendance"."attended_children" AS "attended_children",
        "daily_attendance"."attended_children_percent" AS "attended_children_percent",
        "daily_attendance"."form_location" AS "form_location",
        "daily_attendance"."form_location_lat" AS "form_location_lat",
        "daily_attendance"."form_location_long" AS "form_location_long",
        "daily_attendance"."image_name" AS "image_name"
    FROM "public"."awc_location_months" "awc_location_months"
    LEFT JOIN "public"."daily_attendance" "daily_attendance" ON (
        ("awc_location_months"."awc_id" = "daily_attendance"."awc_id") AND
        ("awc_location_months"."month" = "daily_attendance"."month")
    );

DROP VIEW IF EXISTS agg_awc_daily_view CASCADE;
CREATE VIEW agg_awc_daily_view AS
    SELECT
        "awc_location"."doc_id" AS "awc_id",
        "awc_location"."awc_name" AS "awc_name",
        "awc_location"."awc_site_code" AS "awc_site_code",
        "awc_location"."supervisor_id" AS "supervisor_id",
        "awc_location"."supervisor_name" AS "supervisor_name",
        "awc_location"."supervisor_site_code" AS "supervisor_site_code",
        "awc_location"."block_id" AS "block_id",
        "awc_location"."block_name" AS "block_name",
        "awc_location"."block_site_code" AS "block_site_code",
        "awc_location"."district_id" AS "district_id",
        "awc_location"."district_name" AS "district_name",
        "awc_location"."district_site_code" AS "district_site_code",
        "awc_location"."state_id" AS "state_id",
        "awc_location"."state_name" AS "state_name",
        "awc_location"."state_site_code" AS "state_site_code",
        "awc_location"."aggregation_level" AS "aggregation_level",
        "agg_awc"."date" AS "date",
        COALESCE("agg_awc"."cases_household", 0) AS "cases_household",
        COALESCE("agg_awc"."cases_person", 0) AS "cases_person",
        COALESCE("agg_awc"."cases_person_all", 0) AS "cases_person_all",
        COALESCE("agg_awc"."cases_person_has_aadhaar", 0) AS "cases_person_has_aadhaar",
        COALESCE("agg_awc"."cases_person_adolescent_girls_11_14", 0) AS "cases_person_adolescent_girls_11_14",
        COALESCE("agg_awc"."cases_person_adolescent_girls_15_18", 0) AS "cases_person_adolescent_girls_15_18",
        COALESCE("agg_awc"."cases_person_adolescent_girls_11_14_all", 0) AS "cases_person_adolescent_girls_11_14_all",
        COALESCE("agg_awc"."cases_person_adolescent_girls_15_18_all", 0) AS "cases_person_adolescent_girls_15_18_all",
        COALESCE("agg_awc"."cases_person_adolescent_girls_11_14", 0) + COALESCE("agg_awc"."cases_person_adolescent_girls_15_18", 0) AS "cases_person_adolescent_girls_11_18",
        COALESCE("agg_awc"."cases_person_adolescent_girls_11_14_all", 0) + COALESCE("agg_awc"."cases_person_adolescent_girls_15_18_all", 0) AS "cases_person_adolescent_girls_11_18_all",
        COALESCE("agg_awc"."cases_ccs_pregnant", 0) AS "cases_ccs_pregnant",
        COALESCE("agg_awc"."cases_ccs_lactating", 0) AS "cases_ccs_lactating",
        COALESCE("agg_awc"."cases_child_health", 0) AS "cases_child_health",
        COALESCE("agg_awc"."cases_ccs_pregnant_all", 0) AS "cases_ccs_pregnant_all",
        COALESCE("agg_awc"."cases_ccs_lactating_all", 0) AS "cases_ccs_lactating_all",
        COALESCE("agg_awc"."cases_child_health_all", 0) AS "cases_child_health_all",
        COALESCE("agg_awc"."daily_attendance_open", 0) AS "daily_attendance_open",
        "agg_awc"."num_awcs" AS "num_awcs",
        "agg_awc"."num_launched_states" AS "num_launched_states",
        "agg_awc"."num_launched_districts" AS "num_launched_districts",
        "agg_awc"."num_launched_blocks" AS "num_launched_blocks",
        "agg_awc"."num_launched_supervisors" AS "num_launched_supervisors",
        "agg_awc"."num_launched_awcs" AS "num_launched_awcs"
    FROM "public"."awc_location" "awc_location"
    LEFT JOIN "public"."agg_awc_daily" "agg_awc" ON (
        ("awc_location"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location"."state_id" = "agg_awc"."state_id") AND
        ("awc_location"."district_id" = "agg_awc"."district_id") AND
        ("awc_location"."block_id" = "agg_awc"."block_id") AND
        ("awc_location"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location"."doc_id" = "agg_awc"."awc_id")
    );

DROP VIEW IF EXISTS child_health_monthly_view CASCADE;
CREATE VIEW child_health_monthly_view AS
    SELECT
        "child_list".case_id,
        "child_list".awc_id,
        "child_list".name AS person_name,
        "child_list".mother_name,
        "child_list".opened_on,
        "child_list".closed_on,
        "child_list".closed,
        "child_list".dob,
        "child_list".sex,
        "child_list".fully_immunized_date,
        child_health_monthly.month,
        child_health_monthly.age_in_months,
        child_health_monthly.open_in_month,
        child_health_monthly.valid_in_month,
        child_health_monthly.wer_eligible,
        child_health_monthly.valid_all_registered_in_month,
        child_health_monthly.nutrition_status_last_recorded,
        child_health_monthly.current_month_nutrition_status,
        child_health_monthly.nutrition_status_weighed,
        child_health_monthly.num_rations_distributed,
        child_health_monthly.pse_eligible,
        child_health_monthly.pse_days_attended,
        child_health_monthly.born_in_month,
        child_health_monthly.recorded_weight,
        child_health_monthly.recorded_height,
        child_health_monthly.thr_eligible,
        child_health_monthly.stunting_last_recorded,
        child_health_monthly.current_month_stunting,
        child_health_monthly.wasting_last_recorded,
        child_health_monthly.current_month_wasting
   FROM "config_report_icds-cas_static-child_health_cases_a46c129f" "child_list"
     LEFT JOIN child_health_monthly child_health_monthly ON "child_list".case_id = child_health_monthly.case_id;