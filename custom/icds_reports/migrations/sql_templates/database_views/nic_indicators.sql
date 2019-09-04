DROP VIEW IF EXISTS nic_indicators CASCADE;
CREATE VIEW nic_indicators AS
SELECT
    "awc_monthly"."state_id" AS "state_id",
    "awc_monthly"."state_name" AS "state_name",
    "awc_monthly"."month" AS "month",
    "awc_monthly"."cases_household",
    "awc_monthly"."cases_ccs_pregnant",
    "awc_monthly"."cases_ccs_lactating",
    "awc_monthly"."cases_child_health",
    "awc_monthly"."num_launched_awcs",
    "child_health"."ebf_in_month",
    "child_health"."cf_initiation_in_month",
    "child_health"."bf_at_birth"
FROM "agg_awc_monthly" "awc_monthly"
LEFT JOIN (
    SELECT
        state_id, month, aggregation_level,
        sum(ebf_in_month) as ebf_in_month,
        sum(cf_initiation_in_month) as cf_initiation_in_month,
        sum(bf_at_birth) as bf_at_birth
    FROM
        "agg_child_health_monthly"
    WHERE
        aggregation_level=1
    GROUP BY
        state_id, month, aggregation_level
) "child_health" ON (
        ("awc_monthly"."month" = "child_health"."month") AND
        ("awc_monthly"."aggregation_level" = "child_health"."aggregation_level") AND
        ("awc_monthly"."state_id" = "child_health"."state_id")
    )
WHERE
    "awc_monthly"."aggregation_level"=1;
