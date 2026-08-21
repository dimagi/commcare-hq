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
/* Custom Scan (Citus INSERT ... SELECT via coordinator)  (cost=0.00..0.00 rows=0 width=0)
   ->  Unique  (cost=0.00..0.00 rows=0 width=0)
         ->  Sort  (cost=0.00..0.00 rows=0 width=0)
               Sort Key: remote_scan.case_id
               ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
                     Task Count: 64
                     Tasks Shown: One of 64
                     ->  Task
                           Node: host=100.71.184.232 port=6432 dbname=icds_ucr
                           ->  Unique  (cost=506909.94..508506.42 rows=113291 width=155)
                                 ->  Sort  (cost=506909.94..507708.18 rows=319296 width=155)
                                       Sort Key: "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea".child_health_case_id
                                       ->  WindowAgg  (cost=439533.21..448313.85 rows=319296 width=155)
                                             ->  Sort  (cost=439533.21..440331.45 rows=319296 width=113)
                                                   Sort Key: "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea".supervisor_id, "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea".child_health_case_id
                                                   ->  Gather  (cost=1000.00..387329.01 rows=319296 width=113)
                                                         Workers Planned: 6
                                                         ->  Parallel Seq Scan on "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea_104058" "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea"  (cost=0.00..354399.41 rows=53216 width=113)
                                                               Filter: ((child_health_case_id IS NOT NULL) AND (timeend >= '2020-02-01 00:00:00'::timestamp without time zone) AND (timeend < '2020-03-01 00:00:00'::timestamp without time zone))*/
