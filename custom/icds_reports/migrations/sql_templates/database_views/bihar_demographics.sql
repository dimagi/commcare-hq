DROP VIEW IF EXISTS bihar_demographics_view CASCADE;
CREATE VIEW bihar_demographics_view AS
    SELECT
        "bihar_demographics"."awc_id" AS "awc_id",
        "awc_location"."awc_name" AS "awc_name",
        "awc_location"."awc_site_code" AS "awc_site_code",
        "bihar_demographics"."supervisor_id" AS "supervisor_id",
        "awc_location"."supervisor_name" AS "supervisor_name",
        "awc_location"."supervisor_site_code" AS "supervisor_site_code",
        "bihar_demographics"."block_id" AS "block_id",
        "awc_location"."block_name" AS "block_name",
        "awc_location"."block_site_code" AS "block_site_code",
        "bihar_demographics"."district_id" AS "district_id",
        "awc_location"."district_name" AS "district_name",
        "awc_location"."district_site_code" AS "district_site_code",
        "bihar_demographics"."state_id" AS "state_id",
        "awc_location"."state_name" AS "state_name",
        "awc_location"."state_site_code" AS "state_site_code",
        CONCAT(
            COALESCE("awc_location"."awc_ward_1", ''), ' ',
            COALESCE("awc_location"."awc_ward_2", ''), ' ',
            COALESCE("awc_location"."awc_ward_3", '')
            ) AS ward_number,
        "bihar_demographics"."month" AS "month",
        "bihar_demographics"."household_id" AS "household_id",
        "bihar_demographics"."household_name" AS "household_name",
        "bihar_demographics"."hh_reg_date" AS "hh_reg_date",
        "bihar_demographics"."hh_num" AS "hh_num",
        "bihar_demographics"."hh_gps_location" AS "hh_gps_location",
        "bihar_demographics"."hh_caste" AS "hh_caste",
        "bihar_demographics"."hh_bpl_apl" AS "hh_bpl_apl",
        "bihar_demographics"."hh_minority" AS "hh_minority",
        "bihar_demographics"."hh_religion" AS "hh_religion",
        "bihar_demographics"."hh_member_number" AS "hh_member_number",
        "bihar_demographics"."person_id" AS "person_id",
        "bihar_demographics"."person_name" AS "person_name",
        "bihar_demographics"."has_adhaar" AS "has_adhaar",
        "bihar_demographics"."bank_account_number" AS "bank_account_number",
        "bihar_demographics"."ifsc_code" AS "ifsc_code",
        "bihar_demographics"."age_at_reg" AS "age_at_reg",
        "bihar_demographics"."dob" AS "dob",
        "bihar_demographics"."gender" AS "gender",
        "bihar_demographics"."blood_group" AS "blood_group",
        "bihar_demographics"."disabled" AS "disabled",
        "bihar_demographics"."disability_type" AS "disability_type",
        "bihar_demographics"."referral_status" AS "referral_status",
        "bihar_demographics"."migration_status" AS "migration_status",
        "bihar_demographics"."resident" AS "resident",
        "bihar_demographics"."registered_status" AS "registered_status",
        "bihar_demographics"."rch_id" AS "rch_id",
        "bihar_demographics"."mcts_id" AS "mcts_id",
        "bihar_demographics"."phone_number" AS "phone_number",
        "bihar_demographics"."date_death" AS "date_death",
        "bihar_demographics"."site_death" AS "site_death",
        "bihar_demographics"."closed_on" AS "closed_on",
        "bihar_demographics"."reason_closure" AS "reason_closure"
    FROM "public"."bihar_api_demographics" "bihar_demographics"
    LEFT JOIN "public"."awc_location" "awc_location"
    ON (
        ("awc_location"."supervisor_id" = "bihar_demographics"."supervisor_id") AND
        ("awc_location"."doc_id" = "bihar_demographics"."awc_id")
    );
