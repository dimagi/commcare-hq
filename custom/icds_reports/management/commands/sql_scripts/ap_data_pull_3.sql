COPY(SELECT
    awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code,
    SUM(CASE WHEN chm.num_rations_distributed>=21 AND chm.month='%(month_1)s' THEN 1 ELSE 0 END) as thr_count_ccs_%(column_1)s,
    SUM(CASE WHEN chm.thr_eligible=1 AND chm.month='%(month_1)s' THEN 1 ELSE 0 END) as thr_eligible_ccs_%(column_1)s,

    SUM(CASE WHEN chm.num_rations_distributed>=21 AND chm.month='%(month_2)s' THEN 1 ELSE 0 END) as thr_count_ccs_%(column_2)s,
    SUM(CASE WHEN chm.thr_eligible=1 AND chm.month='%(month_2)s' THEN 1 ELSE 0 END) as thr_eligible_ccs_%(column_2)s,

    SUM(CASE WHEN chm.num_rations_distributed>=21 AND chm.month='%(month_3)s' THEN 1 ELSE 0 END) as thr_count_ccs_%(column_3)s,
    SUM(CASE WHEN chm.thr_eligible=1 AND chm.month='%(month_3)s' THEN 1 ELSE 0 END) as thr_eligible_ccs_%(column_3)s
FROM
    "awc_location" awc LEFT JOIN "ccs_record_monthly" chm ON (
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
    awc.awc_site_code) TO '/tmp/%(name)s/ap_data_pull_3.csv' DELIMITER ',' CSV HEADER


--                                                                                    QUERY PLAN
-- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.state_name, remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.awc_name, remote_scan.awc_site_code
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  GroupAggregate  (cost=176133.36..176133.43 rows=1 width=136)
--                      Group Key: awc.state_name, awc.district_name, awc.block_name, awc.supervisor_name, awc.awc_name, awc.awc_site_code
--                      ->  Sort  (cost=176133.36..176133.36 rows=1 width=100)
--                            Sort Key: awc.state_name, awc.district_name, awc.block_name, awc.supervisor_name, awc.awc_name, awc.awc_site_code
--                            ->  Gather  (cost=1000.55..176133.35 rows=1 width=100)
--                                  Workers Planned: 5
--                                  ->  Nested Loop  (cost=0.55..175133.25 rows=1 width=100)
--                                        ->  Parallel Seq Scan on ccs_record_monthly_102712 chm  (cost=0.00..137867.58 rows=29125 width=78)
--                                              Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                                        ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc  (cost=0.55..1.27 rows=1 width=151)
--                                              Index Cond: (doc_id = chm.awc_id)
--                                              Filter: ((state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (aggregation_level = 5) AND (chm.supervisor_id = supervisor_id))
