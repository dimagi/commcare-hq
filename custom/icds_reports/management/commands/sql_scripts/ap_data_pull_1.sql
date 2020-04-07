COPY(SELECT
    awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code,
    SUM(CASE WHEN chm.nutrition_status_weighed=1 AND chm.age_tranche::int<=36 AND month='%(month_1)s' THEN 1 ELSE 0 END) as weight_recorded_%(column_1)s,
    SUM(CASE WHEN chm.wer_eligible=1 AND chm.age_tranche::int<=36 AND month='%(month_1)s' THEN 1 ELSE 0 END) as weight_eligible_%(column_1)s,
    SUM(CASE WHEN chm.num_rations_distributed>=21 AND month='%(month_1)s' THEN 1 ELSE 0 END) as thr_count_%(column_1)s,
    SUM(CASE WHEN chm.thr_eligible=1 AND month='%(month_1)s' THEN 1 ELSE 0 END) as thr_eligible_%(column_1)s,

    SUM(CASE WHEN chm.nutrition_status_weighed=1 AND chm.age_tranche::int<=36 AND month='%(month_2)s' THEN 1 ELSE 0 END) as weight_recorded_%(column_2)s,
    SUM(CASE WHEN chm.wer_eligible=1 AND chm.age_tranche::int<=36 AND month='%(month_2)s' THEN 1 ELSE 0 END) as weight_eligible_%(column_2)s,
    SUM(CASE WHEN chm.num_rations_distributed>=21 AND month='%(month_3)s' THEN 1 ELSE 0 END) as thr_count_%(column_2)s,
    SUM(CASE WHEN chm.thr_eligible=1 AND month='%(month_2)s' THEN 1 ELSE 0 END) as thr_eligible_%(column_2)s,

    SUM(CASE WHEN chm.nutrition_status_weighed=1 AND chm.age_tranche::int<=36 AND month='%(month_3)s' THEN 1 ELSE 0 END) as weight_recorded_%(column_3)s,
    SUM(CASE WHEN chm.wer_eligible=1 AND chm.age_tranche::int<=36 AND month='%(month_3)s' THEN 1 ELSE 0 END) as weight_eligible_%(column_3)s,
    SUM(CASE WHEN chm.num_rations_distributed>=21 AND month='%(month_3)s' THEN 1 ELSE 0 END) as thr_count_%(column_3)s,
    SUM(CASE WHEN chm.thr_eligible=1 AND month='%(month_3)s' THEN 1 ELSE 0 END) as thr_eligible_%(column_3)s
FROM
    "awc_location" awc LEFT JOIN "child_health_monthly" chm ON (
        chm.supervisor_id=awc.supervisor_id and
        chm.awc_id = awc.doc_id
    )
    where chm.month in ('%(month_1)s','%(month_2)s','%(month_3)s')
    and awc.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc.aggregation_level=5
GROUP by awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code) TO '/tmp/%(name)s/ap_data_pull_1.csv' DELIMITER ',' CSV HEADER

--                                                                                               QUERY PLAN
-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.state_name, remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.awc_name, remote_scan.awc_site_code
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=606131.60..606132.45 rows=4 width=184)
--                      Group Key: awc.state_name, awc.district_name, awc.block_name, awc.supervisor_name, awc.awc_name, awc.awc_site_code
--                      ->  Gather Merge  (cost=606131.60..606132.23 rows=4 width=176)
--                            Workers Planned: 4
--                            ->  Partial GroupAggregate  (cost=605131.54..605131.70 rows=1 width=176)
--                                  Group Key: awc.state_name, awc.district_name, awc.block_name, awc.supervisor_name, awc.awc_name, awc.awc_site_code
--                                  ->  Sort  (cost=605131.54..605131.55 rows=1 width=110)
--                                        Sort Key: awc.state_name, awc.district_name, awc.block_name, awc.supervisor_name, awc.awc_name, awc.awc_site_code
--                                        ->  Nested Loop  (cost=6108.68..605131.53 rows=1 width=110)
--                                              ->  Parallel Bitmap Heap Scan on awc_location_102840 awc  (cost=6108.12..49812.70 rows=13801 width=151)
--                                                    Recheck Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
--                                                    Filter: (aggregation_level = 5)
--                                                    ->  Bitmap Index Scan on awc_location_pkey_102840  (cost=0.00..6094.32 rows=57592 width=0)
--                                                          Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
--                                              ->  Append  (cost=0.56..40.23 rows=1 width=88)
--                                                    ->  Index Scan using child_health_monthly_default_102648_awc_id_idx on child_health_monthly_default_102648 chm  (cost=0.56..40.22 rows=1 width=88)
--                                                          Index Cond: (awc_id = awc.doc_id)
--                                                          Filter: ((awc.supervisor_id = supervisor_id) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[])))
