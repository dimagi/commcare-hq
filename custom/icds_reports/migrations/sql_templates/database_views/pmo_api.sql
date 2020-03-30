DROP VIEW IF EXISTS pmo_api_view CASCADE;
CREATE VIEW pmo_api_view AS
    SELECT
        "awc_location_months"."district_id" AS "district_id",
        "awc_location_months"."district_name" AS "district_name",
        "awc_location_months"."district_site_code" AS "district_site_code",
        "awc_location_months"."state_id" AS "state_id",
        "awc_location_months"."state_name" AS "state_name",
        "awc_location_months"."state_site_code" AS "state_site_code",
        "awc_location_months"."aggregation_level" AS "aggregation_level",
        "awc_location_months"."month" AS "month",
        "agg_awc"."cbe_conducted" AS "cbe_conducted",
        "agg_awc"."vhnd_conducted" AS "vhnd_conducted",
        "agg_awc"."num_launched_awcs" AS "num_launched_awcs",
        "agg_awc"."wer_eligible" AS "wer_eligible",
        "agg_awc"."wer_weighed" AS "wer_weighed",
        SUM("agg_child_health"."bf_at_birth") as "bf_at_birth",
        SUM("agg_child_health"."born_in_month") as "born_in_month",
        SUM("agg_child_health"."cf_initiation_in_month") as "cf_initiation_in_month",
        SUM("agg_child_health"."cf_initiation_eligible") as "cf_initiation_eligible"
    FROM "public"."awc_location_months_local" "awc_location_months"
    LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("agg_awc"."aggregation_level" = 2)
        )
    LEFT JOIN "public"."agg_child_health" "agg_child_health" ON (
        ("awc_location_months"."month" = "agg_child_health"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_child_health"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_child_health"."state_id") AND
        ("awc_location_months"."district_id" = "agg_child_health"."district_id") AND
        ("agg_child_health"."aggregation_level" = 2)
        )
    WHERE
        "awc_location_months"."aggregation_level" = 2 AND
        "agg_awc"."state_is_test" <> 1 AND
        "agg_awc"."district_is_test" <> 1
    GROUP BY
        "awc_location_months"."district_id",
        "awc_location_months"."district_name",
        "awc_location_months"."district_site_code",
        "awc_location_months"."state_id",
        "awc_location_months"."state_name",
        "awc_location_months"."state_site_code",
        "awc_location_months"."aggregation_level",
        "awc_location_months"."month",
        "agg_awc"."cbe_conducted",
        "agg_awc"."vhnd_conducted",
        "agg_awc"."num_launched_awcs",
        "agg_awc"."wer_eligible",
        "agg_awc"."wer_weighed"
