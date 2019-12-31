COPY(SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,
    CASE WHEN SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-04-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0 END as pw_thr_21_April,
    CASE WHEN SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-05-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as pw_thr_21_May,
    CASE WHEN SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-06-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as pw_thr_21_June,
    CASE WHEN SUM(CASE WHEN month='2019-07-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-07-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-07-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as pw_thr_21_July,
    CASE WHEN SUM(CASE WHEN month='2019-08-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-08-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-08-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as pw_thr_21_Aug,
    CASE WHEN SUM(CASE WHEN month='2019-09-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-09-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-09-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as pw_thr_21_Sept,
    CASE WHEN SUM(CASE WHEN month='2019-10-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-10-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-10-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as pw_thr_21_Oct,
    CASE WHEN SUM(CASE WHEN month='2019-11-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-11-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-11-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as pw_thr_21_Nov
FROM
    awc_location  LEFT JOIN  "ccs_record_monthly"  ON (
        ccs_record_monthly.supervisor_id=awc_location.supervisor_id and
        ccs_record_monthly.awc_id = awc_location.doc_id AND
        ccs_record_monthly.pregnant=1
    )
    where month in ('2019-04-01', '2019-05-01', '2019-06-01', '2019-07-01','2019-08-01','2019-09-01','2019-10-01', '2019-11-01')
and   awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc_location.aggregation_level=5
GROUP by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code) TO '/tmp/pw_thr_april_to_Nov.csv' DELIMITER ',' CSV HEADER
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

    CASE WHEN SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-04-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0 END as lw_thr_21_April,
    CASE WHEN SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-05-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as lw_thr_21_May,
    CASE WHEN SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-06-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as lw_thr_21_June,
    CASE WHEN SUM(CASE WHEN month='2019-07-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-07-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-07-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as lw_thr_21_July,
    CASE WHEN SUM(CASE WHEN month='2019-08-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-08-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-08-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as lw_thr_21_Aug,
    CASE WHEN SUM(CASE WHEN month='2019-09-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-09-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-09-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as lw_thr_21_Sept,
    CASE WHEN SUM(CASE WHEN month='2019-10-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-10-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-10-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as lw_thr_21_Oct,
    CASE WHEN SUM(CASE WHEN month='2019-11-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-11-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-11-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as lw_thr_21_Nov
FROM
    awc_location  LEFT JOIN  "ccs_record_monthly"  ON (
        ccs_record_monthly.supervisor_id=awc_location.supervisor_id and
        ccs_record_monthly.awc_id = awc_location.doc_id and  lactating=1
    )
    where month in ('2019-04-01', '2019-05-01', '2019-06-01', '2019-07-01','2019-08-01','2019-09-01','2019-10-01', '2019-11-01')
 and awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc_location.aggregation_level=5
GROUP by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code) TO '/tmp/lw_thr_april_to_Nov.csv' DELIMITER ',' CSV HEADER




COPY(SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,

    CASE WHEN SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-04-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-04-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0 END as child_thr_21_April,
    CASE WHEN SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-05-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-05-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as child_thr_21_May,
    CASE WHEN SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-06-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-06-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as child_thr_21_June,
    CASE WHEN SUM(CASE WHEN month='2019-07-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-07-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-07-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as child_thr_21_July,
    CASE WHEN SUM(CASE WHEN month='2019-08-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-08-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-08-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as child_thr_21_Aug,
    CASE WHEN SUM(CASE WHEN month='2019-09-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-09-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-09-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as child_thr_21_Sept,
    CASE WHEN SUM(CASE WHEN month='2019-10-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-10-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-10-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as child_thr_21_Oct,
    CASE WHEN SUM(CASE WHEN month='2019-11-01'  THEN thr_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN num_rations_distributed>=21 AND month='2019-11-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-11-01'  THEN thr_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as child_thr_21_Nov

FROM
    awc_location LEFT JOIN "child_health_monthly"  ON (
        child_health_monthly.supervisor_id=awc_location.supervisor_id and
        child_health_monthly.awc_id = awc_location.doc_id and
        child_health_monthly.thr_eligible=1
    )
    where month in ('2019-04-01', '2019-05-01', '2019-06-01', '2019-07-01','2019-08-01','2019-09-01','2019-10-01', '2019-11-01')
    and awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc_location.aggregation_level=5
GROUP by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code) TO '/tmp/child_thr_april_to_Nov.csv' DELIMITER ',' CSV HEADER
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



COPY(SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,

    CASE WHEN SUM(CASE WHEN month='2019-04-01'  THEN wer_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN nutrition_status_weighed=1 AND month='2019-04-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-04-01'  THEN wer_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0 END as growth_monitoring_April,
    CASE WHEN SUM(CASE WHEN month='2019-05-01'  THEN wer_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN nutrition_status_weighed=1 AND month='2019-05-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-05-01'  THEN wer_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as growth_monitoring_May,
    CASE WHEN SUM(CASE WHEN month='2019-06-01'  THEN wer_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN nutrition_status_weighed=1 AND month='2019-06-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-06-01'  THEN wer_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as growth_monitoring_June,
    CASE WHEN SUM(CASE WHEN month='2019-07-01'  THEN wer_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN nutrition_status_weighed=1 AND month='2019-07-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-07-01'  THEN wer_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as growth_monitoring_July,
    CASE WHEN SUM(CASE WHEN month='2019-08-01'  THEN wer_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN nutrition_status_weighed=1 AND month='2019-08-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-08-01'  THEN wer_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as growth_monitoring_Aug,
    CASE WHEN SUM(CASE WHEN month='2019-09-01'  THEN wer_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN nutrition_status_weighed=1 AND month='2019-09-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-09-01'  THEN wer_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as growth_monitoring_Sept,
    CASE WHEN SUM(CASE WHEN month='2019-10-01'  THEN wer_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN nutrition_status_weighed=1 AND month='2019-10-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-10-01'  THEN wer_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as growth_monitoring_Oct,
    CASE WHEN SUM(CASE WHEN month='2019-11-01'  THEN wer_eligible ELSE 0 END)>0 THEN round((sum(CASE WHEN nutrition_status_weighed=1 AND month='2019-11-01'  THEN 1 ELSE 0 END)/SUM(CASE WHEN month='2019-11-01'  THEN wer_eligible ELSE 0 END)::float)::numeric,2)*100 ELSE 0  END as growth_monitoring_Nov

FROM
   awc_location LEFT JOIN "child_health_monthly"  ON (
        child_health_monthly.supervisor_id=awc_location.supervisor_id and
        child_health_monthly.awc_id = awc_location.doc_id and wer_eligible=1
    )
    where month in ('2019-04-01', '2019-05-01', '2019-06-01', '2019-07-01','2019-08-01','2019-09-01','2019-10-01', '2019-11-01')
    and awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc_location.aggregation_level=5
and  age_tranche::INTEGER<=36
GROUP by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code) TO '/tmp/child_gm_april_to_Nov.csv' DELIMITER ',' CSV HEADER



COPY(
    SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,
    SUM(CASE WHEN month='2019-04-01' THEN num_awcs_conducted_vhnd ELSE 0 END) as conducted_vhnd_april,
    SUM(CASE WHEN month='2019-05-01' THEN num_awcs_conducted_vhnd ELSE 0 END) as conducted_vhnd_may,
    SUM(CASE WHEN month='2019-06-01' THEN num_awcs_conducted_vhnd ELSE 0 END) as conducted_vhnd_june,
    SUM(CASE WHEN month='2019-07-01' THEN num_awcs_conducted_vhnd ELSE 0 END) as conducted_vhnd_July,
    SUM(CASE WHEN month='2019-08-01' THEN num_awcs_conducted_vhnd ELSE 0 END) as conducted_vhnd_August,
    SUM(CASE WHEN month='2019-09-01' THEN num_awcs_conducted_vhnd ELSE 0 END) as conducted_vhnd_september,
    SUM(CASE WHEN month='2019-10-01' THEN num_awcs_conducted_vhnd ELSE 0 END) as conducted_vhnd_oct,
    SUM(CASE WHEN month='2019-11-01' THEN num_awcs_conducted_vhnd ELSE 0 END) as conducted_vhnd_nov,

    SUM(CASE WHEN month='2019-04-01' THEN COALESCE(thr_rations_21_plus_distributed_child,0) + COALESCE(num_mother_thr_21_days,0) ELSE 0 end) as thr_21_total_april,
    SUM(CASE WHEN month='2019-04-01' THEN COALESCE(thr_eligible_child,0) + COALESCE(num_mother_thr_eligible,0) ELSE 0 end) as total_eligible_eligible_april,

    SUM(CASE WHEN month='2019-05-01' THEN COALESCE(thr_rations_21_plus_distributed_child,0) + COALESCE(num_mother_thr_21_days,0) ELSE 0 end) as thr_21_total_may,
    SUM(CASE WHEN month='2019-05-01' THEN COALESCE(thr_eligible_child,0) + COALESCE(num_mother_thr_eligible,0) ELSE 0 end) as total_eligible_eligible_may,
    SUM(CASE WHEN month='2019-06-01' THEN COALESCE(thr_rations_21_plus_distributed_child,0) + COALESCE(num_mother_thr_21_days,0) ELSE 0 end) as thr_21_total_june,
    SUM(CASE WHEN month='2019-06-01' THEN COALESCE(thr_eligible_child,0) + COALESCE(num_mother_thr_eligible,0) ELSE 0 end) as total_eligible_eligible_june,
    SUM(CASE WHEN month='2019-07-01' THEN COALESCE(thr_rations_21_plus_distributed_child,0) + COALESCE(num_mother_thr_21_days,0) ELSE 0 end) as thr_21_total_july,
    SUM(CASE WHEN month='2019-07-01' THEN COALESCE(thr_eligible_child,0) + COALESCE(num_mother_thr_eligible,0) ELSE 0 end) as total_eligible_eligible_july,
    SUM(CASE WHEN month='2019-08-01' THEN COALESCE(thr_rations_21_plus_distributed_child,0) + COALESCE(num_mother_thr_21_days,0) ELSE 0 end) as thr_21_total_aug,
    SUM(CASE WHEN month='2019-08-01' THEN COALESCE(thr_eligible_child,0) + COALESCE(num_mother_thr_eligible,0) ELSE 0 end) as total_eligible_eligible_aug,
    SUM(CASE WHEN month='2019-09-01' THEN COALESCE(thr_rations_21_plus_distributed_child,0) + COALESCE(num_mother_thr_21_days,0) ELSE 0 end) as thr_21_total_sept,
    SUM(CASE WHEN month='2019-09-01' THEN COALESCE(thr_eligible_child,0) + COALESCE(num_mother_thr_eligible,0) ELSE 0 end) as total_eligible_eligible_sept,
    SUM(CASE WHEN month='2019-10-01' THEN COALESCE(thr_rations_21_plus_distributed_child,0) + COALESCE(num_mother_thr_21_days,0) ELSE 0 end) as thr_21_total_oct,
    SUM(CASE WHEN month='2019-10-01' THEN COALESCE(thr_eligible_child,0) + COALESCE(num_mother_thr_eligible,0) ELSE 0 end) as total_eligible_eligible_oct,
    SUM(CASE WHEN month='2019-11-01' THEN COALESCE(thr_rations_21_plus_distributed_child,0) + COALESCE(num_mother_thr_21_days,0) ELSE 0 end) as thr_21_total_nov,
    SUM(CASE WHEN month='2019-11-01' THEN COALESCE(thr_eligible_child,0) + COALESCE(num_mother_thr_eligible,0) ELSE 0 end) as total_eligible_eligible_nov

    from awc_location_local awc_location
    left join agg_awc ON(
        awc_location.doc_id = agg_awc.awc_id AND
        awc_location.state_id = agg_awc.state_id AND
        awc_location.district_id = agg_awc.district_id AND
        awc_location.block_id = agg_awc.block_id AND
        awc_location.supervisor_id = agg_awc.supervisor_id AND
        awc_location.aggregation_level = agg_awc.aggregation_level
    )
    where month in ('2019-04-01', '2019-05-01', '2019-06-01', '2019-07-01','2019-08-01','2019-09-01','2019-10-01', '2019-11-01')
    and awc_location.aggregation_level=5 and  awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039'
    group by  state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code
)  TO '/tmp/total_thr_vhnd.csv' DELIMITER ',' CSV HEADER
/*
 GroupAggregate  (cost=527239.26..527239.39 rows=1 width=215)
   Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, awc_location.awc_site_code
   ->  Sort  (cost=527239.26..527239.26 rows=1 width=103)
         Sort Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, awc_location.awc_site_code
         ->  Gather  (cost=52014.01..527239.25 rows=1 width=103)
               Workers Planned: 4
               ->  Parallel Hash Join  (cost=51014.01..526239.15 rows=1 width=103)
                     Hash Cond: (("agg_awc_2019-06-01_5".awc_id = awc_location.doc_id) AND ("agg_awc_2019-06-01_5".district_id = awc_location.district_id) AND ("agg_awc_2019-06-01_5".block_id = awc_location.block_id) AND ("agg_awc_2019-06-01_5".supervisor_id = awc_location.supervisor_id))
                     ->  Parallel Append  (cost=0.68..467547.37 rows=113852 width=185)
                           ->  Parallel Bitmap Heap Scan on "agg_awc_2019-06-01_5"  (cost=15805.69..59574.34 rows=15513 width=185)
                                 Recheck Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                 Filter: ((aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                                 ->  Bitmap Index Scan on "agg_awc_2019-06-01_5_state_id_district_id_block_id_supervi_idx1"  (cost=0.00..15790.17 rows=62053 width=0)
                                       Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                           ->  Parallel Bitmap Heap Scan on "agg_awc_2019-05-01_5"  (cost=12429.01..50112.46 rows=13962 width=185)
                                 Recheck Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                 Filter: ((aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                                 ->  Bitmap Index Scan on "agg_awc_2019-05-01_5_state_id_district_id_block_id_supervi_idx1"  (cost=0.00..12415.05 rows=55850 width=0)
                                       Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                           ->  Parallel Index Scan using "agg_awc_2019-09-01_5_state_id_district_id_block_id_supervis_idx" on "agg_awc_2019-09-01_5"  (cost=0.68..70272.08 rows=13918 width=185)
                                 Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                 Filter: ((aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                           ->  Parallel Index Scan using "agg_awc_2019-07-01_5_state_id_district_id_block_id_supervi_idx1" on "agg_awc_2019-07-01_5"  (cost=0.68..70104.35 rows=14028 width=185)
                                 Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                 Filter: ((aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                           ->  Parallel Index Scan using "agg_awc_2019-08-01_5_state_id_district_id_block_id_supervis_idx" on "agg_awc_2019-08-01_5"  (cost=0.68..69065.55 rows=14056 width=185)
                                 Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                 Filter: ((aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                           ->  Parallel Index Scan using "agg_awc_2019-10-01_5_state_id_district_id_block_id_supervis_idx" on "agg_awc_2019-10-01_5"  (cost=0.68..54738.25 rows=14550 width=185)
                                 Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                 Filter: ((aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                           ->  Parallel Index Scan using "agg_awc_2019-11-01_5_state_id_district_id_block_id_supervis_idx" on "agg_awc_2019-11-01_5"  (cost=0.68..49042.50 rows=13932 width=185)
                                 Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                 Filter: ((aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                           ->  Parallel Seq Scan on "agg_awc_2019-04-01_5"  (cost=0.00..44068.58 rows=13893 width=185)
                                 Filter: ((state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                           ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=180)
                                 Filter: ((state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (aggregation_level = 5) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01,2019-07-01,2019-08-01,2019-09-01,2019-10-01,2019-11-01}'::date[])))
                     ->  Parallel Hash  (cost=50254.23..50254.23 rows=14005 width=251)
                           ->  Parallel Bitmap Heap Scan on awc_location_local awc_location  (cost=6758.99..50254.23 rows=14005 width=251)
                                 Recheck Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                                 Filter: (aggregation_level = 5)
                                 ->  Bitmap Index Scan on awc_location_local_pkey  (cost=0.00..6744.98 rows=58401 width=0)
                                       Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
(44 rows)
 */
