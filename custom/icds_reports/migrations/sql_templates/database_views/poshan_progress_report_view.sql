DROP VIEW IF EXISTS poshan_progress_report_view CASCADE;
CREATE VIEW poshan_progress_report_view AS
    SELECT
        "awc_location_months"."district_id" AS "district_id",
        "awc_location_months"."district_name" AS "district_name",
        "awc_location_months"."state_id" AS "state_id",
        "awc_location_months"."state_name" AS "state_name",
        "awc_location_months"."month" AS "month",
        "awc_location_months"."aggregation_level" AS "aggregation_level",
        COALESCE("agg_awc"."num_launched_districts", 0) AS "num_launched_districts",
        COALESCE("agg_awc"."num_launched_blocks", 0) AS "num_launched_blocks",
        COALESCE("agg_awc"."num_launched_awcs", 0) AS "num_launched_awcs",
        CASE WHEN COALESCE("agg_awc"."num_launched_awcs", 0)>0 THEN "agg_awc"."awc_days_open"/("agg_awc"."num_launched_awcs" * 25)::float*100 ELSE 0 END as "avg_days_awc_open_percent",
        COALESCE("agg_awc"."wer_eligible", 0) AS "wer_eligible",
        COALESCE("agg_awc"."wer_weighed", 0) AS "wer_weighed",
        CASE WHEN COALESCE("agg_awc"."wer_eligible", 0)=0 THEN 0
            ELSE "agg_awc"."wer_weighed"/"agg_awc"."wer_eligible"::float*100 END AS "weighed_percent",
        COALESCE("agg_awc"."expected_visits", 0) AS "expected_visits",
        COALESCE("agg_awc"."valid_visits", 0) AS "valid_visits",
        CASE WHEN COALESCE("agg_awc"."expected_visits", 0)=0 THEN 0
            ELSE "agg_awc"."valid_visits"/"agg_awc"."expected_visits"::float*100 END AS "visits_percent",
        COALESCE("agg_awc"."thr_eligible_child", 0) + COALESCE("agg_awc"."thr_eligible_ccs", 0) AS "thr_eligible",
        COALESCE("agg_awc"."thr_rations_21_plus_distributed_child", 0) + COALESCE("agg_awc"."thr_rations_21_plus_distributed_ccs", 0) AS "thr_rations_21_plus_distributed",
        CASE WHEN (COALESCE("agg_awc"."thr_eligible_child", 0) + COALESCE("agg_awc"."thr_eligible_ccs", 0))=0 THEN 0
            ELSE (COALESCE("agg_awc"."thr_rations_21_plus_distributed_child", 0) + COALESCE("agg_awc"."thr_rations_21_plus_distributed_ccs", 0))/(COALESCE("agg_awc"."thr_eligible_child", 0) + COALESCE("agg_awc"."thr_eligible_ccs", 0))::float*100 END AS "thr_percent",
        COALESCE(SUM("agg_child_health"."pse_eligible"), 0) AS "pse_eligible",
        COALESCE(SUM("agg_child_health"."pse_attended_21_days"), 0) AS "pse_attended_21_days",
        CASE WHEN COALESCE(SUM("agg_child_health"."pse_eligible"), 0)=0 THEN 0
            ELSE SUM("agg_child_health"."pse_attended_21_days")/SUM("agg_child_health"."pse_eligible")::float*100 END as "pse_attended_21_days_percent",
        COALESCE(SUM("agg_child_health"."pse_eligible"), 0) AS "lunch_eligible",
        COALESCE(SUM("agg_child_health"."lunch_count_21_days"), 0) AS "lunch_count_21_days",
        CASE WHEN COALESCE(SUM("agg_child_health"."pse_eligible"), 0)=0 THEN 0
            ELSE SUM("agg_child_health"."lunch_count_21_days")/SUM("agg_child_health"."pse_eligible")::float*100 END as "lunch_count_21_days_percent",
        COALESCE(SUM("agg_child_health"."height_eligible"), 0) AS "height_eligible",
        COALESCE(SUM("agg_child_health"."height_measured_in_month"), 0) AS "height_measured_in_month",
        CASE WHEN COALESCE(SUM("agg_child_health"."height_eligible"), 0)=0 THEN 0
            ELSE SUM("agg_child_health"."height_measured_in_month")/SUM("agg_child_health"."height_eligible")::float*100 END as "height_measured_in_month_percent",
        COALESCE("agg_ccs_record"."trimester_3", 0) AS "trimester_3",
        COALESCE("agg_ccs_record"."counsel_immediate_bf", 0) AS "counsel_immediate_bf",
        CASE WHEN COALESCE("agg_ccs_record"."trimester_3", 0)=0 THEN 0
            ELSE "agg_ccs_record"."counsel_immediate_bf"/"agg_ccs_record"."trimester_3"::float*100 END as "counsel_immediate_bf_percent"
    FROM "public"."awc_location_months_local" "awc_location_months"
    LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id") AND
        ("agg_awc"."aggregation_level" <= 2)
    )
    LEFT JOIN agg_child_health on (
        ("agg_child_health"."month" = "awc_location_months"."month") AND
        ("agg_child_health"."state_id" = "awc_location_months"."state_id") AND
        ("agg_child_health"."district_id" = "awc_location_months"."district_id") AND
        ("agg_child_health"."aggregation_level" = "awc_location_months"."aggregation_level") AND
        ("agg_child_health"."aggregation_level" <= 2)
    )
    LEFT JOIN (
        SELECT
            state_id,
            district_id,
            aggregation_level,
            month,
            SUM(trimester_3) AS trimester_3,
            SUM(counsel_immediate_bf) AS counsel_immediate_bf
            FROM "public"."agg_ccs_record"
            WHERE aggregation_level <= 2
            GROUP BY state_id, district_id, aggregation_level, month
        ) "agg_ccs_record" ON (
            ("awc_location_months"."month" = "agg_ccs_record"."month") AND
            ("awc_location_months"."aggregation_level" = "agg_ccs_record"."aggregation_level") AND
            ("awc_location_months"."state_id" = "agg_ccs_record"."state_id") AND
            ("awc_location_months"."district_id" = "agg_ccs_record"."district_id")
    )
WHERE "awc_location_months"."aggregation_level" <= 2
GROUP BY
    "awc_location_months"."district_id",
    "awc_location_months"."district_name",
    "awc_location_months"."state_id",
    "awc_location_months"."state_name",
    "awc_location_months"."month",
    "awc_location_months"."aggregation_level",
    "agg_awc"."num_launched_districts",
    "agg_awc"."num_launched_blocks",
    "agg_awc"."num_launched_awcs",
    "agg_awc"."awc_days_open",
    "agg_awc"."wer_eligible",
    "agg_awc"."wer_weighed",
    "agg_awc"."expected_visits",
    "agg_awc"."valid_visits",
    "agg_awc"."thr_eligible_child",
    "agg_awc"."thr_eligible_ccs",
    "agg_awc"."thr_rations_21_plus_distributed_child",
    "agg_awc"."thr_rations_21_plus_distributed_ccs",
    "agg_ccs_record"."trimester_3",
    "agg_ccs_record"."counsel_immediate_bf";
