DROP VIEW IF EXISTS bihar_api_mother_view CASCADE;
CREATE VIEW bihar_api_mother_view AS
    SELECT
        "bihar_api_mother_details"."state_id" AS "state_id",
        "bihar_api_mother_details"."supervisor_id" AS "supervisor_id",
        "bihar_api_mother_details"."month" AS "month",
        "bihar_api_mother_details"."ccs_case_id" AS "ccs_case_id",
        "bihar_api_mother_details"."person_id" AS "person_id",
        "bihar_api_mother_details"."household_id" AS "household_id",
        "bihar_api_mother_details"."married" AS "married",
        "bihar_api_mother_details"."husband_name" AS "husband_name",
        "bihar_api_mother_details"."husband_id" AS "husband_id",
        "bihar_api_mother_details"."last_preg_year" AS "last_preg_year",
        "bihar_api_mother_details"."last_preg_tt" AS "last_preg_tt",
        "bihar_api_mother_details"."is_pregnant" AS "is_pregnant",
        CASE WHEN "bihar_api_mother_details"."is_pregnant"=1 THEN
        "ccs_record_monthly"."opened_on" ELSE NULL END AS "preg_reg_date",
        "bihar_api_mother_details"."tt_booster" AS "tt_booster",
        "ccs_record_monthly"."tt_1" AS "tt_1",
        "ccs_record_monthly"."tt_2" AS "tt_2",
        "ccs_record_monthly"."anemia" AS "hb",
        "ccs_record_monthly"."add" AS "add"
    FROM "public"."bihar_api_mother_details" 
    LEFT JOIN "public"."ccs_record_monthly" 
    ON (
        ("ccs_record_monthly"."supervisor_id" = "bihar_api_mother_details"."supervisor_id") AND
        ("ccs_record_monthly"."case_id" = "bihar_api_mother_details"."ccs_case_id") AND
        ("ccs_record_monthly"."month" = "bihar_api_mother_details"."month")
    );
