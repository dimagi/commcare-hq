DROP VIEW IF EXISTS daily_indicators CASCADE;
CREATE VIEW daily_indicators AS
    SELECT
        "awc_location"."state_id" AS "state_id",
        "awc_location"."state_name" AS "state_name",
        "agg_awc"."date" AS "date",
        COALESCE("agg_child".pse_eligible, 0) as pse_eligible,
        COALESCE("agg_awc"."total_attended_pse", 0) AS "total_attended_pse",
        "agg_awc"."num_launched_awcs" AS "num_launched_awcs",
        "agg_awc"."daily_attendance_open" AS "daily_attendance_open"
    FROM "public"."awc_location_local" "awc_location"
    LEFT JOIN "public"."agg_awc_daily" "agg_awc" ON (
        ("awc_location"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location"."state_id" = "agg_awc"."state_id") AND
        ("awc_location"."district_id" = "agg_awc"."district_id") AND
        ("awc_location"."block_id" = "agg_awc"."block_id") AND
        ("awc_location"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location"."doc_id" = "agg_awc"."awc_id")
    )
    LEFT JOIN
      (
        SELECT
            month,
            state_id,
            aggregation_level,
            SUM(pse_eligible) as pse_eligible
            from "agg_child_health"
            where aggregation_level=1
            group by state_id, month, aggregation_level
      ) agg_child ON (
        ("awc_location"."aggregation_level" = "agg_child"."aggregation_level") AND
        ("awc_location"."state_id" = "agg_child"."state_id") AND
        (date_trunc('MONTH',("agg_awc"."date")) = "agg_child"."month")
    )
    WHERE
        "awc_location"."aggregation_level"=1 AND
        "awc_location"."state_is_test"<>1;
