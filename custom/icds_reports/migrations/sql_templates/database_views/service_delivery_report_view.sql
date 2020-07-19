DROP VIEW IF EXISTS service_delivery_report CASCADE;
CREATE VIEW service_delivery_report AS
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
"awc_location_months"."block_map_location_name" AS "block_map_location_name",
"awc_location_months"."district_map_location_name" AS "district_map_location_name",
"awc_location_months"."state_map_location_name" AS "state_map_location_name",
"awc_location_months"."aggregation_level" AS "aggregation_level",
"awc_location_months"."aww_name" AS "aww_name",
"awc_location_months"."contact_phone_number" AS "contact_phone_number",
"awc_location_months"."month" as month,
COALESCE(agg_awc.num_launched_awcs, 0) AS num_launched_awcs,
COALESCE(agg_awc.valid_visits,0) AS valid_visits,
COALESCE(agg_awc.expected_visits,0) AS expected_visits,
COALESCE(agg_awc.num_awcs_conducted_cbe,0) AS num_awcs_conducted_cbe,
COALESCE(agg_awc.num_awcs_conducted_vhnd,0) AS num_awcs_conducted_vhnd,
COALESCE(agg_awc.cbe_conducted,0) as cbe_conducted,
COALESCE(agg_awc.vhnd_conducted,0) as vhnd_conducted,
COALESCE(agg_awc.thr_distribution_image_count,0) as thr_distribution_image_count,
COALESCE(agg_sdr.pse_eligible,0) as pse_eligible,
COALESCE(agg_sdr.pse_0_days,0) as pse_0_days,
COALESCE(agg_sdr.pse_1_7_days,0) as pse_1_7_days,
COALESCE(agg_sdr.pse_8_14_days,0) as pse_8_14_days,
COALESCE(agg_sdr.pse_15_20_days,0) as pse_15_20_days,
COALESCE(agg_sdr.pse_21_days,0) as pse_21_days,
COALESCE(agg_sdr.pse_21_24_days,0) as pse_21_24_days,
COALESCE(agg_sdr.pse_25_days,0) as pse_25_days,
COALESCE(agg_sdr.lunch_eligible,0) as lunch_eligible,
COALESCE(agg_sdr.lunch_0_days,0) as lunch_0_days,
COALESCE(agg_sdr.lunch_1_7_days,0) as lunch_1_7_days,
COALESCE(agg_sdr.lunch_8_14_days,0) as lunch_8_14_days,
COALESCE(agg_sdr.lunch_15_20_days,0) as lunch_15_20_days,
COALESCE(agg_sdr.lunch_21_days,0) as lunch_21_days,
COALESCE(agg_sdr.lunch_21_24_days,0) as lunch_21_24_days,
COALESCE(agg_sdr.lunch_25_days,0) as lunch_25_days,
COALESCE(agg_sdr.thr_eligible,0) as thr_eligible,
COALESCE(agg_sdr.thr_0_days,0) as thr_0_days,
COALESCE(agg_sdr.thr_1_7_days,0) as thr_1_7_days,
COALESCE(agg_sdr.thr_8_14_days,0) as thr_8_14_days,
COALESCE(agg_sdr.thr_15_20_days,0) as thr_15_20_days,
COALESCE(agg_sdr.thr_21_days,0) as thr_21_days,
COALESCE(agg_sdr.thr_21_24_days,0) as thr_21_24_days,
COALESCE(agg_sdr.thr_25_days,0) as thr_25_days,
COALESCE(agg_sdr.child_thr_eligible) as child_thr_eligible,
COALESCE(agg_sdr.child_thr_0_days) as child_thr_0_days,
COALESCE(agg_sdr.child_thr_1_7_days) as child_thr_1_7_days,
COALESCE(agg_sdr.child_thr_8_14_days) as child_thr_8_14_days,
COALESCE(agg_sdr.child_thr_15_20_days) as child_thr_15_20_days,
COALESCE(agg_sdr.child_thr_21_days) as child_thr_21_days,
COALESCE(agg_sdr.child_thr_21_24_days) as child_thr_21_24_days,
COALESCE(agg_sdr.child_thr_25_days) as child_thr_25_days,

COALESCE(agg_sdr.pw_thr_eligible) as pw_thr_eligible,
COALESCE(agg_sdr.pw_thr_0_days) as pw_thr_0_days,
COALESCE(agg_sdr.pw_thr_1_7_days) as pw_thr_1_7_days,
COALESCE(agg_sdr.pw_thr_8_14_days) as pw_thr_8_14_days,
COALESCE(agg_sdr.pw_thr_15_20_days) as pw_thr_15_20_days,
COALESCE(agg_sdr.pw_thr_21_days) as pw_thr_21_days,
COALESCE(agg_sdr.pw_thr_21_24_days) as pw_thr_21_24_days,
COALESCE(agg_sdr.pw_thr_25_days) as pw_thr_25_days,

COALESCE(agg_sdr.lw_thr_eligible) as lw_thr_eligible,
COALESCE(agg_sdr.lw_thr_0_days) as lw_thr_0_days,
COALESCE(agg_sdr.lw_thr_1_7_days) as lw_thr_1_7_days,
COALESCE(agg_sdr.lw_thr_8_14_days) as lw_thr_8_14_days,
COALESCE(agg_sdr.lw_thr_15_20_days) as lw_thr_15_20_days,
COALESCE(agg_sdr.lw_thr_21_days) as lw_thr_21_days,
COALESCE(agg_sdr.lw_thr_21_24_days) as lw_thr_21_24_days,
COALESCE(agg_sdr.lw_thr_25_days) as lw_thr_25_days,

COALESCE(agg_sdr.gm_0_3,0) as gm_0_3,
COALESCE(agg_sdr.gm_3_5,0) as gm_3_5,
COALESCE(agg_sdr.children_0_3,0) as children_0_3,
COALESCE(agg_sdr.children_3_5,0) as children_3_5,
COALESCE(agg_sdr.third_fourth_month_of_pregnancy_count,0) as third_fourth_month_of_pregnancy_count,
COALESCE(agg_sdr.annaprasan_diwas_count,0) as annaprasan_diwas_count,
COALESCE(agg_sdr.suposhan_diwas_count,0) as suposhan_diwas_count,
COALESCE(agg_sdr.coming_of_age_count,0) as coming_of_age_count,
COALESCE(agg_sdr.public_health_message_count,0) as public_health_message_count,

COALESCE(agg_sdr.breakfast_served,0) as breakfast_served,
COALESCE(agg_sdr.hcm_served,0) as hcm_served,
COALESCE(agg_sdr.thr_served,0) as thr_served,
COALESCE(agg_sdr.pse_provided,0) as pse_provided,
COALESCE(agg_sdr.breakfast_21_days,0) as breakfast_21_days,
COALESCE(agg_sdr.hcm_21_days,0) as hcm_21_days,
COALESCE(agg_sdr.breakfast_9_days,0) as breakfast_9_days,
COALESCE(agg_sdr.hcm_9_days,0) as hcm_9_days,
COALESCE(agg_sdr.pse_9_days,0) as pse_9_days,
COALESCE(agg_sdr.pse_16_days,0) as pse_16_days,
COALESCE (agg_awc.awc_days_open,0) as awc_days_open
FROM "public"."awc_location_months_local" "awc_location_months"
LEFT join agg_awc on (
        ("agg_awc"."month" = "awc_location_months"."month") AND
        ("agg_awc"."state_id" = "awc_location_months"."state_id") AND
        ("agg_awc"."district_id" = "awc_location_months"."district_id") AND
        ("agg_awc"."block_id" = "awc_location_months"."block_id") AND
        ("agg_awc"."supervisor_id" = "awc_location_months"."supervisor_id") AND
        ("agg_awc"."aggregation_level" = "awc_location_months"."aggregation_level") AND
        ("agg_awc"."awc_id" = "awc_location_months"."awc_id")
)
LEFT JOIN agg_service_delivery_report agg_sdr on (
        ("agg_sdr"."month" = "awc_location_months"."month") AND
        ("agg_sdr"."state_id" = "awc_location_months"."state_id") AND
        ("agg_sdr"."district_id" = "awc_location_months"."district_id") AND
        ("agg_sdr"."block_id" = "awc_location_months"."block_id") AND
        ("agg_sdr"."supervisor_id" = "awc_location_months"."supervisor_id") AND
        ("agg_sdr"."aggregation_level" = "awc_location_months"."aggregation_level") AND
        ("agg_sdr"."awc_id" = "awc_location_months"."awc_id")
)
