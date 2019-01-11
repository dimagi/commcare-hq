DROP VIEW IF EXISTS icds_disha_indicators CASCADE;
CREATE VIEW icds_disha_indicators AS
SELECT
    "awc_monthly"."block_id" AS "block_id",
    "awc_monthly"."block_name" AS "block_name",
    "awc_monthly"."district_id" AS "district_id",
    "awc_monthly"."district_name" AS "district_name",
    "awc_monthly"."state_id" AS "state_id",
    "awc_monthly"."state_name" AS "state_name",
    "awc_monthly"."aggregation_level" AS "aggregation_level",
    "awc_monthly"."month" AS "month",
    "awc_monthly"."cases_household",
    "awc_monthly"."cases_person_all",
    "awc_monthly"."cases_person",
    "awc_monthly"."cases_ccs_pregnant",
    "awc_monthly"."cases_ccs_lactating",
    "awc_monthly"."cases_child_health_all",
    "awc_monthly"."cases_child_health",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE 100 * "awc_monthly"."infra_medicine_kits" / "awc_monthly"."num_awc_infra_last_update" END as "medicine_kit_percent",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE 100 * "awc_monthly"."infra_infant_weighing_scale" / "awc_monthly"."num_awc_infra_last_update" END as "infant_weighing_scale_percent",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE 100 * "awc_monthly"."infra_adult_weighing_scale" / "awc_monthly"."num_awc_infra_last_update" END as "adult_weighing_scale_percent",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE 100 * "awc_monthly"."infra_clean_water" / "awc_monthly"."num_awc_infra_last_update" END as "clean_water_percent",
    CASE WHEN "awc_monthly"."num_awc_infra_last_update"=0 THEN null
        ELSE 100 * "awc_monthly"."infra_functional_toilet" / "awc_monthly"."num_awc_infra_last_update" END as "functional_toilet_percent",
    CASE WHEN "ccs_record"."pregnant"=0 THEN null
        ELSE 100 * "ccs_record"."resting_during_pregnancy"/"ccs_record"."pregnant" END as "resting_during_pregnancy_percent",
    CASE WHEN "ccs_record"."pregnant"=0 THEN null
        ELSE 100 * "ccs_record"."extra_meal"/"ccs_record"."pregnant" END as "extra_meal_percent",
    CASE WHEN "ccs_record"."trimester_3"=0 THEN null
        ELSE 100 * "ccs_record"."counsel_immediate_bf"/"ccs_record"."trimester_3" END as "counsel_immediate_bf_percent",
    CASE WHEN "child_health"."wer_eligible"=0 THEN null 
        ELSE 100 * "child_health"."nutrition_status_weighed"/"child_health"."wer_eligible" END as "nutrition_status_weighed_percent",
    CASE WHEN "child_health"."height_eligible"=0 THEN null 
        ELSE 100 * "child_health"."height_measured_in_month"/"child_health"."height_eligible" END as "height_measured_in_month_percent",
    nutrition_status_unweighed,
    CASE WHEN "child_health"."nutrition_status_weighed"=0 THEN null 
        ELSE 100 * "child_health"."nutrition_status_severely_underweight"/"child_health"."nutrition_status_weighed" END as "nutrition_status_severely_underweight_percent",
    CASE WHEN "child_health"."nutrition_status_weighed"=0 THEN null 
        ELSE 100 * "child_health"."nutrition_status_moderately_underweight"/"child_health"."nutrition_status_weighed" END as "nutrition_status_moderately_underweight_percent",
    CASE WHEN "child_health"."weighed_and_height_measured_in_month"=0 THEN null 
        ELSE 100 * "child_health"."wasting_severe"/"child_health"."weighed_and_height_measured_in_month" END as "wasting_severe_percent",
    CASE WHEN "child_health"."weighed_and_height_measured_in_month"=0 THEN null 
        ELSE 100 * "child_health"."wasting_moderate"/"child_health"."weighed_and_height_measured_in_month" END as "wasting_moderate_percent",
    CASE WHEN "child_health"."height_measured_in_month"=0 THEN null 
        ELSE 100 * "child_health"."stunting_severe"/"child_health"."height_measured_in_month" END as "stunting_severe_percent",
    CASE WHEN  "child_health"."height_measured_in_month"=0 THEN null 
        ELSE 100 * "child_health"."stunting_moderate"/"child_health"."height_measured_in_month" END as "stunting_moderate_percent"
FROM "agg_awc_monthly" "awc_monthly"
LEFT JOIN (
    SELECT 
        state_id, district_id, block_id, month, aggregation_level,
        sum(pregnant) as pregnant,
        sum(trimester_3) as trimester_3,
        sum(resting_during_pregnancy) as resting_during_pregnancy,
        sum(counsel_immediate_bf) as counsel_immediate_bf,
        sum(extra_meal) as extra_meal
    FROM
        "agg_ccs_record_monthly"
    WHERE
        aggregation_level in (1, 2, 3)
    GROUP BY
        state_id, district_id, block_id, month, aggregation_level
)"ccs_record" ON (
        ("awc_monthly"."month" = "ccs_record"."month") AND
        ("awc_monthly"."aggregation_level" = "ccs_record"."aggregation_level") AND
        ("awc_monthly"."state_id" = "ccs_record"."state_id") AND
        ("awc_monthly"."district_id" = "ccs_record"."district_id") AND
        ("awc_monthly"."block_id" = "ccs_record"."block_id")
    )
LEFT JOIN (
    SELECT
        state_id, district_id, block_id, month, aggregation_level,
        sum(wer_eligible) as wer_eligible,
        sum(height_eligible) as height_eligible,
        sum(height_measured_in_month) as height_measured_in_month,
        sum(nutrition_status_weighed) as nutrition_status_weighed,
        sum(nutrition_status_unweighed) as nutrition_status_unweighed,
        sum(nutrition_status_severely_underweight) as nutrition_status_severely_underweight,
        sum(nutrition_status_moderately_underweight) as nutrition_status_moderately_underweight,
        sum(weighed_and_height_measured_in_month) as weighed_and_height_measured_in_month,
        sum(wasting_severe) as wasting_severe,
        sum(wasting_moderate) as wasting_moderate,
        sum(stunting_severe) as stunting_severe,
        sum(stunting_moderate) as stunting_moderate
    FROM
        "agg_child_health_monthly"
    WHERE
        aggregation_level in (1, 2, 3)
    GROUP BY
        state_id, district_id, block_id, month, aggregation_level
) "child_health" ON (
        ("awc_monthly"."month" = "child_health"."month") AND
        ("awc_monthly"."aggregation_level" = "child_health"."aggregation_level") AND
        ("awc_monthly"."state_id" = "child_health"."state_id") AND
        ("awc_monthly"."district_id" = "child_health"."district_id") AND
        ("awc_monthly"."block_id" = "child_health"."block_id")
    )
WHERE
    "awc_monthly"."aggregation_level" in (1, 2, 3);