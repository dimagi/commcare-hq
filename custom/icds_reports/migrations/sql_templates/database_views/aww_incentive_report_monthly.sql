DROP VIEW IF EXISTS aww_incentive_report_monthly CASCADE;
CREATE VIEW aww_incentive_report_monthly AS
SELECT
      "awc_incentive"."state_id",
      "awc_incentive"."district_id",
      "awc_incentive"."month",
      "awc_incentive"."awc_id",
      "awc_incentive"."block_id",
      "awc_incentive"."supervisor_id",
      "awc_incentive"."state_name",
      "awc_incentive"."district_name",
      "awc_incentive"."block_name",
      "awc_incentive"."supervisor_name",
      "awc_incentive"."awc_name",
      "awc_incentive"."aww_name",
      "awc_incentive"."contact_phone_number",
      "awc_incentive"."wer_weighed",
      "awc_incentive"."wer_eligible",
      "awc_incentive"."awc_num_open",
      "awc_incentive"."valid_visits",
      "awc_incentive"."expected_visits",
      "awc_monthly"."is_launched"

FROM "public"."icds_dashboard_aww_incentive" "awc_incentive"
LEFT JOIN "agg_awc_monthly" "awc_monthly" ON (
  "awc_incentive"."awc_id" = "awc_monthly"."awc_id" AND
  "awc_incentive"."month" = "awc_monthly"."month" AND
  "awc_monthly"."aggregation_level"=5
)


