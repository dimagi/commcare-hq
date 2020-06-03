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
        CASE WHEN "agg_awc"."num_launched_awcs">0 THEN 100 * "agg_awc"."awc_days_open"/("agg_awc"."num_launched_awcs" * 25) ELSE 0 END as "avg_days_awc_open_percent",
        COALESCE("agg_awc"."wer_eligible", 0) AS "wer_eligible",
        COALESCE("agg_awc"."wer_weighed", 0) AS "wer_weighed",
        CASE WHEN COALESCE("agg_awc"."wer_eligible", 0)=0 THEN 0
            ELSE 100 * "agg_awc"."wer_weighed"/"agg_awc"."wer_eligible" END AS "weighed_percent",
        COALESCE("agg_awc"."expected_visits", 0) AS "expected_visits",
        COALESCE("agg_awc"."valid_visits", 0) AS "valid_visits",
        CASE WHEN COALESCE("agg_awc"."expected_visits", 0)=0 THEN 0
            ELSE 100 * "agg_awc"."valid_visits"/"agg_awc"."expected_visits" END AS "visits_percent",
        COALESCE("agg_awc"."thr_eligible_child", 0) + COALESCE("agg_awc"."thr_eligible_ccs", 0) AS "thr_eligible",
        COALESCE("agg_awc"."thr_rations_21_plus_distributed_child", 0) + COALESCE("agg_awc"."thr_rations_21_plus_distributed_ccs", 0) AS "thr_rations_21_plus_distributed",
        CASE WHEN (COALESCE("agg_awc"."thr_eligible_child", 0) + COALESCE("agg_awc"."thr_eligible_ccs", 0))=0 THEN null
            ELSE 100 * (COALESCE("agg_awc"."thr_rations_21_plus_distributed_child", 0) + COALESCE("agg_awc"."thr_rations_21_plus_distributed_ccs", 0))/(COALESCE("agg_awc"."thr_eligible_child", 0) + COALESCE("agg_awc"."thr_eligible_ccs", 0)) END AS "thr_percent",
        COALESCE("agg_child_health"."pse_eligible", 0) AS "pse_eligible",
        COALESCE("agg_child_health"."pse_attended_21_days", 0) AS "pse_attended_21_days",
        CASE WHEN COALESCE("agg_child_health"."pse_eligible", 0)=0 THEN 0
            ELSE 100 * "agg_child_health"."pse_attended_21_days"/"agg_child_health"."pse_eligible" END as "pse_attended_21_days_percent",
        COALESCE("agg_child_health"."pse_eligible", 0) AS "lunch_eligible",
        COALESCE("agg_child_health"."lunch_count_21_days", 0) AS "lunch_count_21_days",
        CASE WHEN COALESCE("agg_child_health"."pse_eligible", 0)=0 THEN 0
            ELSE 100 * "agg_child_health"."lunch_count_21_days"/"agg_child_health"."pse_eligible" END as "lunch_count_21_days_percent",
        COALESCE("agg_child_health"."height_eligible", 0) AS "height_eligible",
        COALESCE("agg_child_health"."height_measured_in_month", 0) AS "height_measured_in_month",
        CASE WHEN COALESCE("agg_child_health"."height_eligible", 0)=0 THEN 0
            ELSE 100 * "agg_child_health"."height_measured_in_month"/"agg_child_health"."height_eligible" END as "height_measured_in_month_percent",
        COALESCE("agg_ccs_record"."trimester_3", 0) AS "trimester_3",
        COALESCE("agg_ccs_record"."counsel_immediate_bf", 0) AS "counsel_immediate_bf",
        CASE WHEN COALESCE("agg_ccs_record"."trimester_3", 0)=0 THEN 0
            ELSE 100 * "agg_ccs_record"."counsel_immediate_bf"/"agg_ccs_record"."trimester_3" END as "counsel_immediate_bf_percent"
    FROM "public"."awc_location_months_local" "awc_location_months"
    LEFT JOIN (
        SELECT
            state_id,
            district_id,
            block_id,
            supervisor_id,
            awc_id,
            aggregation_level,
            month,
            SUM(pse_eligible) AS pse_eligible,
            SUM(pse_attended_21_days) AS pse_attended_21_days,
            SUM(lunch_count_21_days) AS lunch_count_21_days,
            SUM(height_eligible) AS height_eligible,
            SUM(height_measured_in_month) AS height_measured_in_month
            FROM "public"."agg_child_health"
            GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, aggregation_level, month
        ) "agg_child_health" ON (
            ("awc_location_months"."month" = "agg_child_health"."month") AND
            ("awc_location_months"."aggregation_level" = "agg_child_health"."aggregation_level") AND
            ("awc_location_months"."state_id" = "agg_child_health"."state_id") AND
            ("awc_location_months"."district_id" = "agg_child_health"."district_id") AND
            ("awc_location_months"."block_id" = "agg_child_health"."block_id") AND
            ("awc_location_months"."supervisor_id" = "agg_child_health"."supervisor_id") AND
            ("awc_location_months"."awc_id" = "agg_child_health"."awc_id")
    )
    LEFT JOIN (
        SELECT
            state_id,
            district_id,
            block_id,
            supervisor_id,
            awc_id,
            aggregation_level,
            month,
            SUM(trimester_3) AS trimester_3,
            SUM(counsel_immediate_bf) AS counsel_immediate_bf
            FROM "public"."agg_ccs_record"
            GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, aggregation_level, month
        ) "agg_ccs_record" ON (
            ("awc_location_months"."month" = "agg_ccs_record"."month") AND
            ("awc_location_months"."aggregation_level" = "agg_ccs_record"."aggregation_level") AND
            ("awc_location_months"."state_id" = "agg_ccs_record"."state_id") AND
            ("awc_location_months"."district_id" = "agg_ccs_record"."district_id") AND
            ("awc_location_months"."block_id" = "agg_ccs_record"."block_id") AND
            ("awc_location_months"."supervisor_id" = "agg_ccs_record"."supervisor_id") AND
            ("awc_location_months"."awc_id" = "agg_ccs_record"."awc_id")
    )
    LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
    )
