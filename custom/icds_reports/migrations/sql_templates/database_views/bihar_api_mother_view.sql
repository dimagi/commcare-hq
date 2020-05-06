DROP VIEW IF EXISTS bihar_api_mother_view CASCADE;
CREATE VIEW bihar_api_mother_view AS
    SELECT
        "bihar_api_demographics"."state_id" AS "state_id",
        "bihar_api_demographics"."supervisor_id" AS "supervisor_id",
        "ccs_record_monthly"."month" AS "month",
        "ccs_record_monthly"."case_id" AS "ccs_case_id",
        "bihar_api_demographics"."person_id" AS "person_id",
        "bihar_api_demographics"."household_id" AS "household_id",
        "bihar_api_demographics"."married" AS "married",
        "bihar_api_demographics"."husband_name" AS "husband_name",
        "bihar_api_demographics"."husband_id" AS "husband_id",
        "ccs_record_monthly"."last_preg_year" AS "last_preg_year",
        "bihar_api_demographics"."last_preg_tt" AS "last_preg_tt",
        "bihar_api_demographics"."is_pregnant" AS "is_pregnant",
        CASE WHEN "bihar_api_demographics"."is_pregnant"=1 THEN
        "ccs_record_monthly"."opened_on" ELSE NULL END AS "preg_reg_date",
        "ccs_record_monthly"."tt_booster" AS "tt_booster",
        "ccs_record_monthly"."tt_1" AS "tt_1",
        "ccs_record_monthly"."tt_2" AS "tt_2",
        "ccs_record_monthly"."anemia" AS "hb",
        "ccs_record_monthly"."add" AS "add",
        "ccs_record_monthly"."edd" - 280 AS lmp
    from "public"."ccs_record_monthly"
    LEFT JOIN "public"."bihar_api_demographics"
    ON (
        ("ccs_record_monthly"."supervisor_id" = "bihar_api_demographics"."supervisor_id") AND
        ("ccs_record_monthly"."person_case_id" = "bihar_api_demographics"."person_id") AND
        ("ccs_record_monthly"."month" = "bihar_api_demographics"."month")
    );
