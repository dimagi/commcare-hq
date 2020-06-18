DROP VIEW IF EXISTS system_usage_report_view CASCADE;
CREATE VIEW system_usage_report_view AS
    SELECT
        "agg_awc_monthly"."awc_id" AS "awc_id",
        "agg_awc_monthly"."awc_name" AS "awc_name",
        "agg_awc_monthly"."supervisor_id" AS "supervisor_id",
        "agg_awc_monthly"."supervisor_name" AS "supervisor_name",
        "agg_awc_monthly"."block_id" AS "block_id",
        "agg_awc_monthly"."block_name" AS "block_name",
        "agg_awc_monthly"."district_id" AS "district_id",
        "agg_awc_monthly"."district_name" AS "district_name",
        "agg_awc_monthly"."state_id" AS "state_id",
        "agg_awc_monthly"."state_name" AS "state_name",
        "agg_awc_monthly"."aggregation_level" AS "aggregation_level",
        "agg_awc_monthly"."month" AS "month",
        "agg_awc_monthly"."contact_phone_number" AS "contact_phone_number",
        COALESCE("agg_awc_monthly"."awc_days_open", 0) AS "awc_days_open",
        COALESCE("agg_awc_monthly"."num_launched_awcs", 0) AS "num_launched_awcs",
        COALESCE("agg_awc_monthly"."usage_num_hh_reg", 0) AS "usage_num_hh_reg",
        COALESCE("agg_awc_monthly"."usage_num_add_pregnancy", 0) AS "usage_num_add_pregnancy",
        COALESCE("agg_awc_monthly"."usage_num_bp_tri1", 0)+COALESCE("agg_awc_monthly"."usage_num_bp_tri2", 0)+COALESCE("agg_awc_monthly"."usage_num_bp_tri3", 0) AS "usage_num_bp_tri",
        COALESCE("agg_awc_monthly"."usage_num_delivery", 0) AS "usage_num_delivery",
        COALESCE("agg_awc_monthly"."usage_num_pnc", 0) AS "usage_num_pnc",
        COALESCE("agg_awc_monthly"."usage_num_thr", 0) AS "usage_num_thr",
        COALESCE("agg_awc_monthly"."usage_num_ebf", 0) AS "usage_num_ebf",
        COALESCE("agg_awc_monthly"."usage_num_cf", 0) AS "usage_num_cf",
        COALESCE("agg_awc_monthly"."usage_num_gmp", 0) AS "usage_num_gmp",
        COALESCE("agg_awc_monthly"."usage_num_due_list_ccs", 0) + COALESCE("agg_awc_monthly"."usage_num_due_list_child_health", 0) AS "usage_num_due_list_ccs_and_child_health",
        COALESCE("agg_ls"."num_supervisor_launched", 0) AS "num_supervisor_launched",
        "agg_awc_monthly"."num_launched_states" AS "num_launched_states",
        "agg_awc_monthly"."num_launched_districts" AS "num_launched_districts",
        "agg_awc_monthly"."num_launched_blocks" AS "num_launched_blocks",
        "agg_awc_monthly"."num_launched_supervisors" AS "num_launched_supervisors",
        "agg_awc_monthly"."block_map_location_name" AS "block_map_location_name",
        "agg_awc_monthly"."district_map_location_name" AS "district_map_location_name",
        "agg_awc_monthly"."state_map_location_name" AS "state_map_location_name",
        COALESCE("agg_ls"."num_supervisor_launched", 0) AS "num_supervisor_launched",
        "agg_awc_monthly"."app_version" AS "app_version",
        "agg_awc_monthly"."commcare_version" AS "commcare_version"
    FROM "agg_awc_monthly"
    LEFT JOIN agg_ls ON (
        ("agg_awc_monthly"."month" = "agg_ls"."month") AND
        ("agg_awc_monthly"."aggregation_level" = "agg_ls"."aggregation_level") AND
        ("agg_awc_monthly"."state_id" = "agg_ls"."state_id") AND
        ("agg_awc_monthly"."district_id" = "agg_ls"."district_id") AND
        ("agg_awc_monthly"."block_id" = "agg_ls"."block_id") AND
        ("agg_awc_monthly"."supervisor_id" = "agg_ls"."supervisor_id")
    );
