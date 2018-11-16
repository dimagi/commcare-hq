DROP VIEW IF EXISTS agg_ls_report_monthly CASCADE;
CREATE VIEW agg_ls_report_monthly AS
SELECT
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
agg_ls_report.unique_awc_vists as unique_awc_vists,
agg_ls_report.vhnd_observed as vhnd_observed,
agg_ls_report.beneficiary_vists as beneficiary_vists,
agg_ls_report.month as month,
agg_awc.num_launched_awcs as num_launched_awcs
FROM agg_ls_report
inner join agg_awc on (
        ("agg_awc"."month" = "agg_ls_report"."month") AND
        ("agg_awc"."state_id" = "agg_ls_report"."state_id") AND
        ("agg_awc"."district_id" = "agg_ls_report"."district_id") AND
        ("agg_awc"."block_id" = "agg_ls_report"."block_id") AND
        ("agg_awc"."supervisor_id" = "agg_ls_report"."supervisor_id") AND
        ("agg_awc"."aggregation_level" = "agg_ls_report"."aggregation_level")
)
inner join "public"."awc_location_months" "awc_location_months"  on (
        ("awc_location_months"."month" = "agg_ls_report"."month") AND
        ("awc_location_months"."state_id" = "agg_ls_report"."state_id") AND
        ("awc_location_months"."district_id" = "agg_ls_report"."district_id") AND
        ("awc_location_months"."block_id" = "agg_ls_report"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_ls_report"."supervisor_id") AND
        ("awc_location_months"."aggregation_level" = "agg_ls_report"."aggregation_level")
)