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
          WHERE ucr.timeend >= '2019-12-01' AND ucr.timeend < '2020-01-01'
              AND ucr.child_health_case_id IS NOT NULL
              AND ucr.state_id = 'c7985cd779924b62b9eb863cea8e63b7'
          WINDOW w AS (PARTITION BY ucr.supervisor_id, ucr.child_health_case_id)

/*
 Unique  (cost=0.00..0.00 rows=0 width=0)
   ->  Sort  (cost=0.00..0.00 rows=0 width=0)
         Sort Key: remote_scan.case_id
         ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
               Task Count: 64
               Tasks Shown: One of 64
               ->  Task
                     Node: host=100.71.184.232 port=6432 dbname=icds_ucr
                     ->  Unique  (cost=5.63..5.64 rows=1 width=200)
                           ->  Sort  (cost=5.63..5.63 rows=1 width=200)
                                 Sort Key: ucr.child_health_case_id
                                 ->  WindowAgg  (cost=5.58..5.62 rows=1 width=200)
                                       ->  Sort  (cost=5.58..5.59 rows=1 width=148)
                                             Sort Key: ucr.supervisor_id, ucr.child_health_case_id
                                             ->  Nested Loop  (cost=1.12..5.57 rows=1 width=148)
                                                   ->  Index Scan using ix_daily_attendance_month_state_id_102776 on daily_attendance_102776 daily_attendance  (cost=0.43..2.65 rows=1 width=136)
                                                         Index Cond: ((month = '2019-12-01'::date) AND (state_id = 'c7985cd779924b62b9eb863cea8e63b7'::text))
                                                   ->  Index Scan using "ucr_icds-cas_dashboard_child_health_daily_2cd9a7c1_pkey_103098" on "ucr_icds-cas_dashboard_child_health_daily_2cd9a7c1_103098" ucr  (cost=0.69..2.92 rows=1 width=152)
                                                         Index Cond: ((supervisor_id = daily_attendance.supervisor_id) AND (doc_id = daily_attendance.doc_id))
                                                         Filter: ((child_health_case_id IS NOT NULL) AND (timeend >= '2019-12-01 00:00:00'::timestamp without time zone) AND (timeend < '2020-02-01 00:00:00'::timestamp without time zone) AND (state_id = 'c7985cd779924b62b9eb863cea8e63b7'::text))
(20 rows)

 */
