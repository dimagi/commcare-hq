COPY (
select district_name, block_name,awc_name,awc_site_code,
count(*) filter (WHERE pse_days_attended >=1) as pse_Days_atleast_1_day,
count(*) filter (WHERE pse_days_attended >=21) as pse_Days_atleast_21_day
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='2af81d10b2ca4229a54bab97a5150538' and
    awc_location.supervisor_id = child_health.supervisor_id AND
    district_is_test<>1 and
    child_health.month='2019-10-01'
    )
WHERE child_health.pse_eligible=1 and aggregation_level=5
group by  district_name, block_name,awc_name,awc_site_code
) To '/tmp/pse_Oct_3_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.district_name, remote_scan.block_name, remote_scan.awc_name, remote_scan.awc_site_code
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=6432 dbname=icds_ucr
               ->  GroupAggregate  (cost=436013.25..436013.32 rows=2 width=73)
                     Group Key: awc_location.district_name, awc_location.block_name, awc_location.awc_name, awc_location.awc_site_code
                     ->  Sort  (cost=436013.25..436013.26 rows=2 width=61)
                           Sort Key: awc_location.district_name, awc_location.block_name, awc_location.awc_name, awc_location.awc_site_code
                           ->  Gather  (cost=1001.11..436013.24 rows=2 width=61)
                                 Workers Planned: 5
                                 ->  Nested Loop  (cost=1.11..435013.04 rows=1 width=61)
                                       ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..380802.70 rows=60656 width=70)
                                             Index Cond: (month = '2019-10-01'::date)
                                             Filter: (pse_eligible = 1)
                                       ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..0.88 rows=1 width=120)
                                             Index Cond: (doc_id = child_health.awc_id)
                                             Filter: ((district_is_test <> 1) AND (aggregation_level = 5) AND (state_id = '2af81d10b2ca4229a54bab97a5150538'::text) AND (child_health.supervisor_id = supervisor_id))
(20 rows)


 */




COPY (
select district_name, block_name,awc_name,awc_site_code,
count(*) filter (WHERE pse_days_attended >=1) as pse_Days_atleast_1_day,
count(*) filter (WHERE pse_days_attended >=21) as pse_Days_atleast_21_day
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='2af81d10b2ca4229a54bab97a5150538' and
    awc_location.supervisor_id = child_health.supervisor_id AND
    district_is_test<>1 and
    child_health.month='2019-11-01'
    )
WHERE child_health.pse_eligible=1 and aggregation_level=5
group by  district_name, block_name,awc_name,awc_site_code
) To '/tmp/pse_Nov_3_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.district_name, remote_scan.block_name, remote_scan.awc_name, remote_scan.awc_site_code
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=6432 dbname=icds_ucr
               ->  GroupAggregate  (cost=466895.11..466895.18 rows=2 width=73)
                     Group Key: awc_location.district_name, awc_location.block_name, awc_location.awc_name, awc_location.awc_site_code
                     ->  Sort  (cost=466895.11..466895.12 rows=2 width=61)
                           Sort Key: awc_location.district_name, awc_location.block_name, awc_location.awc_name, awc_location.awc_site_code
                           ->  Gather  (cost=1001.11..466895.10 rows=2 width=61)
                                 Workers Planned: 5
                                 ->  Nested Loop  (cost=1.11..465894.90 rows=1 width=61)
                                       ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..407948.18 rows=67016 width=70)
                                             Index Cond: (month = '2019-11-01'::date)
                                             Filter: (pse_eligible = 1)
                                       ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..0.85 rows=1 width=120)
                                             Index Cond: (doc_id = child_health.awc_id)
                                             Filter: ((district_is_test <> 1) AND (aggregation_level = 5) AND (state_id = '2af81d10b2ca4229a54bab97a5150538'::text) AND (child_health.supervisor_id = supervisor_id))
(20 rows)


 */
