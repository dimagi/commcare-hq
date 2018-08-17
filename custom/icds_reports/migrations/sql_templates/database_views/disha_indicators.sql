DROP VIEW IF EXISTS disha_indicators CASCADE;
CREATE VIEW disha_indicators AS
SELECT
    "location_months"."awc_id" AS "awc_id",
    "location_months"."awc_name" AS "awc_name",
    "location_months"."supervisor_id" AS "supervisor_id",
    "location_months"."supervisor_name" AS "supervisor_name",
    "location_months"."block_id" AS "block_id",
    "location_months"."block_name" AS "block_name",
    "location_months"."district_id" AS "district_id",
    "location_months"."district_name" AS "district_name",
    "location_months"."state_id" AS "state_id",
    "location_months"."state_name" AS "state_name",
    "location_months"."aggregation_level" AS "aggregation_level",
    "location_months"."month" AS "month",
    "agg_awc"."cases_household",
    "awc_monthly"."cases_person_all",
    "awc_monthly"."cases_person",
    "awc_monthly"."cases_ccs_pregnant_all",
    "awc_monthly"."cases_ccs_pregnant",
    "awc_monthly"."cases_ccs_lactating_all",
    "awc_monthly"."cases_ccs_lactating",
    "awc_monthly"."cases_child_health_all",
    "awc_monthly"."cases_child_health",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE "awc_monthly"."infra_medicine_kits" / "awc_monthly"."num_awc_infra_last_update" END as "medicine_kit_percent",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE "awc_monthly"."infra_infant_weighing_scale" / "awc_monthly"."num_awc_infra_last_update" END as "infant_weighing_scale_percent",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE "awc_monthly"."infra_adult_weighing_scale" / "awc_monthly"."num_awc_infra_last_update" END as "adult_weighing_scale_percent",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE "awc_monthly"."infra_clean_water" / "awc_monthly"."num_awc_infra_last_update" END as "clean_water_percent",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE "awc_monthly"."infra_functional_toilet" / "awc_monthly"."num_awc_infra_last_update" END as "functional_toilet_percent",
    CASE WHEN "ccs_record"."pregnant"=0 THEN null
        ELSE ("ccs_record"."anemic_moderate" + "ccs_record"."anemic_severe")/"ccs_record"."pregnant" END as "anemic_pregnant_percent",
    CASE WHEN "ccs_record"."pregnant"=0 THEN null
        ELSE "ccs_record"."tetanus_complete"/"ccs_record"."pregnant" END as "tetanus_complete_percent",
    CASE WHEN "ccs_record"."delivered_in_month"=0 THEN null
        ELSE "ccs_record"."anc1_received_at_delivery"/"ccs_record"."delivered_in_month" END as "anc1_received_at_delivery_percent",
    CASE WHEN "ccs_record"."delivered_in_month"=0 THEN null
        ELSE "ccs_record"."anc2_received_at_delivery"/"ccs_record"."delivered_in_month" END as "anc2_received_at_delivery_percent",
    CASE WHEN "ccs_record"."delivered_in_month"=0 THEN null
        ELSE "ccs_record"."anc3_received_at_delivery"/"ccs_record"."delivered_in_month" END as "anc3_received_at_delivery_percent",
    CASE WHEN "ccs_record"."delivered_in_month"=0 THEN null
        ELSE "ccs_record"."anc4_received_at_delivery"/"ccs_record"."delivered_in_month" END as "anc4_received_at_delivery_percent",
    CASE WHEN "ccs_record"."pregnant"=0 THEN null
        ELSE "ccs_record"."resting_during_pregnancy"/"ccs_record"."pregnant" END as "resting_during_pregnancy_percent",
    CASE WHEN "ccs_record"."pregnant"=0 THEN null
        ELSE "ccs_record"."extra_meal"/"ccs_record"."pregnant" END as "extra_meal_percent",
    CASE WHEN "ccs_record"."trimester_3"=0 THEN null
        ELSE ("ccs_record"."counsel_immediate_bf")/"ccs_record"."trimester_3" END as "counsel_immediate_bf_percent",
    CASE WHEN "child_health"."wer_eligible"=0 THEN null 
        ELSE "child_health"."nutrition_status_weighed"/"child_health"."wer_eligible" END as "nutrition_status_weighed_percent",
    CASE WHEN "child_health"."height_eligible"=0 THEN null 
        ELSE "child_health"."height_measured_in_month"/"child_health"."height_eligible" END as "height_measured_in_month_percent",
    nutrition_status_unweighed,
    CASE WHEN "child_health"."nutrition_status_weighed"=0 THEN null 
        ELSE "child_health"."nutrition_status_severely_underweight"/"child_health"."nutrition_status_weighed" END as "nutrition_status_severely_underweight_percent",
    CASE WHEN "child_health"."nutrition_status_weighed"=0 THEN null 
        ELSE "child_health"."nutrition_status_moderately_underweight"/"child_health"."nutrition_status_weighed" END as "nutrition_status_moderately_underweight_percent",
    CASE WHEN "child_health"."weighed_and_height_measured_in_month"=0 THEN null 
        ELSE "child_health"."wasting_severe"/"child_health"."weighed_and_height_measured_in_month" END as "wasting_severe_percent",
    CASE WHEN "child_health"."weighed_and_height_measured_in_month"=0 THEN null 
        ELSE "child_health"."wasting_moderate"/"child_health"."weighed_and_height_measured_in_month" END as "wasting_moderate_percent",
    CASE WHEN "child_health"."height_measured_in_month"=0 THEN null 
        ELSE "child_health"."stunting_severe"/"child_health"."height_measured_in_month" END as "stunting_severe_percent",
    CASE WHEN  "child_health"."height_measured_in_month"=0 THEN null 
        ELSE "child_health"."stunting_moderate"/"child_health"."height_measured_in_month" END as "stunting_moderate_percent",
    CASE WHEN "child_health"."weighed_and_born_in_month"=0 THEN null 
        ELSE "child_health"."low_birth_weight_in_month"/"child_health"."weighed_and_born_in_month" END as "low_birth_weight_in_month_percent",
    CASE WHEN  "child_health"."fully_immunized_eligible"=0 THEN null 
        ELSE ("child_health"."fully_immunized_on_time" + "child_health"."fully_immunized_late")/ "child_health"."fully_immunized_eligible" END as "immunized_percent"    
FROM "awc_location_months" "location_months"
LEFT JOIN "agg_awc" ON (
        ("location_months"."month" = "agg_awc"."month") AND
        ("location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("location_months"."state_id" = "agg_awc"."state_id") AND
        ("location_months"."district_id" = "agg_awc"."district_id") AND
        ("location_months"."block_id" = "agg_awc"."block_id") AND
        ("location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("location_months"."awc_id" = "agg_awc"."awc_id")
    )
LEFT JOIN "agg_awc_monthly" "awc_monthly" ON (
        ("location_months"."month" = "awc_monthly"."month") AND
        ("location_months"."aggregation_level" = "awc_monthly"."aggregation_level") AND
        ("location_months"."state_id" = "awc_monthly"."state_id") AND
        ("location_months"."district_id" = "awc_monthly"."district_id") AND
        ("location_months"."block_id" = "awc_monthly"."block_id") AND
        ("location_months"."supervisor_id" = "awc_monthly"."supervisor_id") AND
        ("location_months"."awc_id" = "awc_monthly"."awc_id")
    )
LEFT JOIN "agg_ccs_record_monthly" "ccs_record" ON (
        ("location_months"."month" = "ccs_record"."month") AND
        ("location_months"."aggregation_level" = "ccs_record"."aggregation_level") AND
        ("location_months"."state_id" = "ccs_record"."state_id") AND
        ("location_months"."district_id" = "ccs_record"."district_id") AND
        ("location_months"."block_id" = "ccs_record"."block_id") AND
        ("location_months"."supervisor_id" = "ccs_record"."supervisor_id") AND
        ("location_months"."awc_id" = "ccs_record"."awc_id")
    )
LEFT JOIN "agg_child_health_monthly" "child_health" ON (
        ("location_months"."month" = "child_health"."month") AND
        ("location_months"."aggregation_level" = "child_health"."aggregation_level") AND
        ("location_months"."state_id" = "child_health"."state_id") AND
        ("location_months"."district_id" = "child_health"."district_id") AND
        ("location_months"."block_id" = "child_health"."block_id") AND
        ("location_months"."supervisor_id" = "child_health"."supervisor_id") AND
        ("location_months"."awc_id" = "child_health"."awc_id")
    );