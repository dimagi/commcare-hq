DROP VIEW IF EXISTS ccs_record_monthly_view CASCADE;
CREATE VIEW ccs_record_monthly_view AS
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
        "awc_location_months"."month" AS "month",
        "ccs_record_monthly"."add" AS "add",
        "ccs_record_monthly"."age_in_months" AS "age_in_months",
        "ccs_record_monthly"."anc_hemoglobin" AS "anc_hemoglobin",
        "ccs_record_monthly"."anc_weight" AS "anc_weight",
        "ccs_record_monthly"."anemic_moderate" AS "anemic_moderate",
        "ccs_record_monthly"."anemic_normal" AS "anemic_normal",
        "ccs_record_monthly"."anemic_severe" AS "anemic_severe",
        "ccs_record_monthly"."anemic_unknown" AS "anemic_unknown",
        "ccs_record_monthly"."bleeding" AS "bleeding",
        "ccs_record_monthly"."blurred_vision" AS "blurred_vision",
        "ccs_record_monthly"."bp_dia" AS "bp_dia",
        "ccs_record_monthly"."bp_sys" AS "bp_sys",
        "ccs_record_monthly"."breastfed_at_birth" AS "breastfed_at_birth",
        "ccs_record_monthly"."case_id" AS "case_id",
        "ccs_record_monthly"."convulsions" AS "convulsions",
        "ccs_record_monthly"."counsel_accessible_postpartum_fp" AS "counsel_accessible_postpartum_fp",
        "ccs_record_monthly"."counsel_bp_vid" AS "counsel_bp_vid",
        "ccs_record_monthly"."counsel_fp_methods" AS "counsel_fp_methods",
        "ccs_record_monthly"."counsel_fp_vid" AS "counsel_fp_vid",
        "ccs_record_monthly"."counsel_immediate_bf" AS "counsel_immediate_bf",
        "ccs_record_monthly"."counsel_immediate_conception" AS "counsel_immediate_conception",
        "ccs_record_monthly"."counsel_preparation" AS "counsel_preparation",
        "ccs_record_monthly"."delivery_nature" AS "delivery_nature",
        "ccs_record_monthly"."edd" AS "edd",
        "ccs_record_monthly"."home_visit_date" AS "home_visit_date",
        "ccs_record_monthly"."ifa_consumed_last_seven_days" AS "ifa_consumed_last_seven_days",
        "ccs_record_monthly"."institutional_delivery_in_month" AS "institutional_delivery_in_month",
        "ccs_record_monthly"."is_ebf" AS "is_ebf",
        "ccs_record_monthly"."last_date_thr" AS "last_date_thr",
        "ccs_record_monthly"."mobile_number" AS "mobile_number",
        "ccs_record_monthly"."num_anc_complete" AS "num_anc_complete",
        "ccs_record_monthly"."num_pnc_visits" AS "num_pnc_visits",
        "ccs_record_monthly"."num_rations_distributed" AS "num_rations_distributed",
        "ccs_record_monthly"."opened_on" AS "opened_on",
        "ccs_record_monthly"."person_name" AS "person_name",
        "ccs_record_monthly"."preg_order" AS "preg_order",
        "ccs_record_monthly"."pregnant" AS "pregnant",
        "ccs_record_monthly"."rupture" AS "rupture",
        "ccs_record_monthly"."swelling" AS "swelling",
        "ccs_record_monthly"."trimester" AS "trimester",
        "ccs_record_monthly"."tt_1" AS "tt_1",
        "ccs_record_monthly"."tt_2" AS "tt_2",
        "ccs_record_monthly"."using_ifa" AS "using_ifa",
        "ccs_record_monthly"."lactating" AS "lactating",
        "ccs_record_monthly"."dob" AS "dob",
        "ccs_record_monthly"."open_in_month" AS "open_in_month",
        "ccs_record_monthly"."closed" AS "closed"
    FROM "public"."awc_location_months" "awc_location_months"
    LEFT JOIN "public"."ccs_record_monthly" "ccs_record_monthly" ON (
        ("awc_location_months"."month" = "ccs_record_monthly"."month") AND
        ("awc_location_months"."awc_id" = "ccs_record_monthly"."awc_id")
    );
