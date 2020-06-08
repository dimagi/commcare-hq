DELETE FROM "icds_dashboard_child_health_thr_forms" where month='2020-02-01';
INSERT INTO "icds_dashboard_child_health_thr_forms" (
          state_id, supervisor_id, month, case_id, latest_time_end_processed, days_ration_given_child
        ) (
          SELECT DISTINCT ON (child_health_case_id)
            state_id AS state_id,
            LAST_VALUE(supervisor_id) over w AS supervisor_id,
            '2020-02-01' AS month,
            child_health_case_id AS case_id,
            MAX(timeend) over w AS latest_time_end_processed,
            CASE WHEN SUM(days_ration_given_child) over w > 32767 THEN 32767 ELSE SUM(days_ration_given_child) over w END AS days_ration_given_child
          FROM "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea"
          WHERE timeend >= '2020-02-01' AND timeend < '2020-03-01' AND
                child_health_case_id IS NOT NULL
          WINDOW w AS (PARTITION BY supervisor_id, child_health_case_id)
          );
