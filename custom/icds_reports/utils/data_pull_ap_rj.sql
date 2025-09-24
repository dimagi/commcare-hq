COPY(SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,
    SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END) as pw_thr_eligible_April,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-04-01'  THEN 1 ELSE 0 END) as pw_rations_distributed_21_April,
    SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END) as pw_thr_eligible_May,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-05-01'  THEN 1 ELSE 0 END)  as pw_rations_distributed_21_May,
    SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END) as pw_thr_eligible_June,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-06-01'  THEN 1 ELSE 0 END)  as pw_rations_distributed_21_June
FROM
    awc_location  LEFT JOIN  "ccs_record_monthly"  ON (
        ccs_record_monthly.supervisor_id=awc_location.supervisor_id and
        ccs_record_monthly.awc_id = awc_location.doc_id AND
        ccs_record_monthly.pregnant=1
    )
    where month in ('2019-04-01', '2019-05-01', '2019-06-01')
and   awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc_location.aggregation_level=5
GROUP by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code) TO '/tmp/pw_thr_april_to_June.csv' DELIMITER ',' CSV HEADER
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.state_name, remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.awc_name, remote_scan.awc_site_code
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=6432 dbname=icds_ucr
               ->  GroupAggregate  (cost=154438.21..154438.38 rows=1 width=279)
                     Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, awc_location.awc_site_code
                     ->  Sort  (cost=154438.21..154438.22 rows=1 width=99)
                           Sort Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, awc_location.awc_site_code
                           ->  Gather  (cost=1000.55..154438.20 rows=1 width=99)
                                 Workers Planned: 5
                                 ->  Nested Loop  (cost=0.55..153438.10 rows=1 width=99)
                                       ->  Parallel Seq Scan on ccs_record_monthly_102712 ccs_record_monthly  (cost=0.00..117495.94 rows=29668 width=78)
                                             Filter: ((pregnant = 1) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                                       ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..1.20 rows=1 width=150)
                                             Index Cond: (doc_id = ccs_record_monthly.awc_id)
                                             Filter: ((state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (aggregation_level = 5) AND (ccs_record_monthly.supervisor_id = supervisor_id))
(19 rows)
 */

COPY(SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,

    SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END) as lw_thr_eligible_April,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-04-01'  THEN 1 ELSE 0 END) as lw_rations_distributed_21_April,
    SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END) as lw_thr_eligible_May,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-05-01'  THEN 1 ELSE 0 END)  as lw_rations_distributed_21_May,
    SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END) as lw_thr_eligible_June,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-06-01'  THEN 1 ELSE 0 END)  as lw_rations_distributed_21_June
FROM
    awc_location  LEFT JOIN  "ccs_record_monthly"  ON (
        ccs_record_monthly.supervisor_id=awc_location.supervisor_id and
        ccs_record_monthly.awc_id = awc_location.doc_id and  lactating=1
    )
    where month in ('2019-04-01', '2019-05-01', '2019-06-01')
 and awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc_location.aggregation_level=5
GROUP by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code) TO '/tmp/lw_thr_april_to_June.csv' DELIMITER ',' CSV HEADER




COPY(SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,

    SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END) as child_thr_eligible_April,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-04-01'  THEN 1 ELSE 0 END) as child_rations_distributed_21_April,
    SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END) as child_thr_eligible_May,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-05-01'  THEN 1 ELSE 0 END)  as child_rations_distributed_21_May,
    SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END) as child_thr_eligible_June,
    SUM(CASE WHEN num_rations_distributed>=21 AND month='2019-06-01'  THEN 1 ELSE 0 END)  as child_rations_distributed_21_June
FROM
    awc_location LEFT JOIN "child_health_monthly"  ON (
        child_health_monthly.supervisor_id=awc_location.supervisor_id and
        child_health_monthly.awc_id = awc_location.doc_id and
        child_health_monthly.thr_eligible=1
    )
    where month in ('2019-04-01', '2019-05-01', '2019-06-01')
    and awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc_location.aggregation_level=5
GROUP by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code) TO '/tmp/child_thr_april_to_June.csv' DELIMITER ',' CSV HEADER
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.state_name, remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.awc_name, remote_scan.awc_site_code
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=6432 dbname=icds_ucr
               ->  Finalize GroupAggregate  (cost=722050.85..722051.80 rows=5 width=279)
                     Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, awc_location.awc_site_code
                     ->  Gather Merge  (cost=722050.85..722051.45 rows=4 width=215)
                           Workers Planned: 4
                           ->  Partial GroupAggregate  (cost=721050.79..721050.92 rows=1 width=215)
                                 Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, awc_location.awc_site_code
                                 ->  Sort  (cost=721050.79..721050.79 rows=1 width=99)
                                       Sort Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, awc_location.awc_site_code
                                       ->  Nested Loop  (cost=6197.83..721050.78 rows=1 width=99)
                                             ->  Parallel Bitmap Heap Scan on awc_location_102840 awc_location  (cost=6197.27..49534.02 rows=13912 width=150)
                                                   Recheck Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                                   Filter: (aggregation_level = 5)
                                                   ->  Bitmap Index Scan on awc_location_pkey_102840  (cost=0.00..6183.36 rows=58025 width=0)
                                                         Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                             ->  Index Scan using chm_awc_idx_102648 on child_health_monthly_102648 child_health_monthly  (cost=0.56..48.26 rows=1 width=78)
                                                   Index Cond: (awc_id = awc_location.doc_id)
                                                   Filter: ((thr_eligible = 1) AND (awc_location.supervisor_id = supervisor_id) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
(24 rows)
 */
