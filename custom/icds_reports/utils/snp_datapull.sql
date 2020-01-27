CREATE TABLE tmp_snp_table AS
SELECT DISTINCT ON (ucr.child_health_case_id)
            ucr.state_id AS state_id,
            ucr.supervisor_id,
            daily_attendance.awc_id,
            '2019-12-01' AS month,
            ucr.child_health_case_id AS case_id,
            MAX(ucr.timeend) OVER w AS latest_time_end_processed,
            SUM(ucr.attended_child_ids) OVER w AS pse_days_attended,
            SUM(ucr.lunch) OVER w AS lunch_days_given,
            SUM(CASE WHEN ucr.attended_child_ids=1 AND ucr.lunch<>1 THEN 1 else 0 END) OVER w AS pse_but_not_lunch
          FROM "ucr_icds-cas_dashboard_child_health_daily_2cd9a7c1" ucr
          INNER JOIN daily_attendance ON (
            ucr.doc_id = daily_attendance.doc_id AND
            ucr.supervisor_id = daily_attendance.supervisor_id AND
            ucr.state_id = daily_attendance.state_id AND
            daily_attendance.month='2019-12-01'
          )
          WHERE ucr.timeend >= '2019-12-01' AND ucr.timeend < '2020-02-01'
              AND ucr.child_health_case_id IS NOT NULL
              AND ucr.state_id = 'c7985cd779924b62b9eb863cea8e63b7'
          WINDOW w AS (PARTITION BY ucr.supervisor_id, ucr.child_health_case_id)
