DROP VIEW IF EXISTS nic_indicators CASCADE;
CREATE VIEW nic_indicators AS
SELECT
    "agg_awc"."state_id" AS "state_id",
    "agg_awc"."state_is_test" AS "state_is_test",
    "awc_location_months"."state_name" AS "state_name",
    "awc_location_months"."state_site_code" AS "state_site_code",
    "agg_awc"."month" AS "month",
    "agg_awc"."cases_household",
    "agg_awc"."cases_ccs_pregnant",
    "agg_awc"."cases_ccs_lactating",
    "agg_awc"."cases_child_health",
    "agg_awc"."num_launched_awcs",
    "child_health"."ebf_in_month",
    "child_health"."cf_initiation_in_month",
    "child_health"."bf_at_birth"
FROM "public"."awc_location_months_local" "awc_location_months"
LEFT JOIN "agg_awc" ON (
        ("agg_awc"."month" = "awc_location_months"."month") AND
        ("agg_awc"."state_id" = "awc_location_months"."state_id") AND
        ("agg_awc"."district_id" = "awc_location_months"."district_id") AND
        ("agg_awc"."block_id" = "awc_location_months"."block_id") AND
        ("agg_awc"."supervisor_id" = "awc_location_months"."supervisor_id") AND
        ("agg_awc"."aggregation_level" = "awc_location_months"."aggregation_level") AND
        ("agg_awc"."awc_id" = "awc_location_months"."awc_id")
)
LEFT JOIN (
    SELECT
        state_id, month, aggregation_level,
        sum(ebf_in_month) as ebf_in_month,
        sum(cf_initiation_in_month) as cf_initiation_in_month,
        sum(bf_at_birth) as bf_at_birth
    FROM
        "agg_child_health"
    WHERE
        aggregation_level=1
    GROUP BY
        state_id, month, aggregation_level
) "child_health" ON (
        ("awc_location_months"."month" = "child_health"."month") AND
        ("awc_location_months"."aggregation_level" = "child_health"."aggregation_level") AND
        ("awc_location_months"."state_id" = "child_health"."state_id")
    )
WHERE
    "agg_awc"."aggregation_level"=1 AND
    "agg_awc"."state_is_test"<>1;
