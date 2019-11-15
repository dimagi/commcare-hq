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
        "awc_location"."block_map_location_name" AS "block_map_location_name",
        "awc_location"."district_map_location_name" AS "district_map_location_name",
        "awc_location"."state_map_location_name" AS "state_map_location_name",
        "awc_location"."aggregation_level" AS "aggregation_level",
        "awc_location"."contact_phone_number" AS "contact_phone_number",
        "agg_awc"."date" AS "date",
        COALESCE("agg_awc"."cases_household", 0) AS "cases_household",
        COALESCE("agg_awc"."cases_person", 0) AS "cases_person",
        COALESCE("agg_awc"."cases_person_all", 0) AS "cases_person_all",
        COALESCE("agg_awc"."cases_person_has_aadhaar", 0) AS "cases_person_has_aadhaar",
        COALESCE("agg_awc"."cases_person_beneficiary", 0) AS "cases_person_beneficiary",
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
        COALESCE("agg_awc"."cases_person_has_aadhaar_v2", 0) AS "cases_person_has_aadhaar_v2",
        COALESCE("agg_awc"."cases_person_beneficiary_v2", 0) AS "cases_person_beneficiary_v2",
        "agg_awc"."num_awcs" AS "num_awcs",
        "agg_awc"."num_launched_states" AS "num_launched_states",
        "agg_awc"."num_launched_districts" AS "num_launched_districts",
        "agg_awc"."num_launched_blocks" AS "num_launched_blocks",
        "agg_awc"."num_launched_supervisors" AS "num_launched_supervisors",
        "agg_awc"."num_launched_awcs" AS "num_launched_awcs"
    FROM "public"."awc_location_local" "awc_location"
    LEFT JOIN "public"."agg_awc_daily" "agg_awc" ON (
        ("awc_location"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location"."state_id" = "agg_awc"."state_id") AND
        ("awc_location"."district_id" = "agg_awc"."district_id") AND
        ("awc_location"."block_id" = "agg_awc"."block_id") AND
        ("awc_location"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location"."doc_id" = "agg_awc"."awc_id")
    );
