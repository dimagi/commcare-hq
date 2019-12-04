
COPY (
select district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as pse_eligible,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended=0 then 1 ELSE 0 END) as pse_0,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended BETWEEN 1 and 7 then 1 ELSE 0 END) as pse_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended BETWEEN 8 and 14 then 1 ELSE 0 END)as  pse_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended between 15 and 21 then 1 ELSE 0 END)as pse_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>21 then 1 ELSE 0 END) as pse_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    awc_location.supervisor_id = child_health.supervisor_id AND
    district_is_test<>1 and
    child_health.month='2019-10-01'
    )
WHERE child_health.age_in_months>36 and aggregation_level=5
group by  district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name, month
) To '/tmp/pse_JULY_3_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*

 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.supervisor_id, remote_scan.awc_name, remote_scan.month
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=5432 dbname=icds_ucr
               ->  GroupAggregate  (cost=466745.98..466746.11 rows=1 width=310)
                     Group Key: awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.supervisor_id, awc_location.awc_name, child_health.month
                     ->  Sort  (cost=466745.98..466745.98 rows=1 width=110)
                           Sort Key: awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.supervisor_id, awc_location.awc_name
                           ->  Gather  (cost=1001.11..466745.97 rows=1 width=110)
                                 Workers Planned: 5
                                 ->  Nested Loop  (cost=1.11..465745.87 rows=1 width=110)
                                       ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..411985.61 rows=61099 width=78)
                                             Index Cond: (month = '2019-10-01'::date)
                                             Filter: (age_in_months > 36)
                                       ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..0.87 rows=1 width=129)
                                             Index Cond: (doc_id = child_health.awc_id)
                                             Filter: ((district_is_test <> 1) AND (aggregation_level = 5) AND (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (child_health.supervisor_id = supervisor_id))
(20 rows)

*/



COPY (
select district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as pse_eligible,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended=0 then 1 ELSE 0 END) as pse_0,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended BETWEEN 1 and 7 then 1 ELSE 0 END) as pse_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended BETWEEN 8 and 14 then 1 ELSE 0 END)as  pse_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended between 15 and 21 then 1 ELSE 0 END)as pse_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>21 then 1 ELSE 0 END) as pse_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    awc_location.supervisor_id = child_health.supervisor_id AND
    district_is_test=0 AND
    child_health.month='2019-10-01'
    )
WHERE child_health.age_in_months>60 and aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/pse_JULY_5_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.supervisor_id, remote_scan.awc_name, remote_scan.month
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=5432 dbname=icds_ucr
               ->  GroupAggregate  (cost=444645.32..444645.46 rows=1 width=310)
                     Group Key: awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.supervisor_id, awc_location.awc_name, child_health.month
                     ->  Sort  (cost=444645.32..444645.33 rows=1 width=110)
                           Sort Key: awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.supervisor_id, awc_location.awc_name
                           ->  Gather  (cost=1001.11..444645.31 rows=1 width=110)
                                 Workers Planned: 5
                                 ->  Nested Loop  (cost=1.11..443645.21 rows=1 width=110)
                                       ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..411985.61 rows=24200 width=78)
                                             Index Cond: (month = '2019-10-01'::date)
                                             Filter: (age_in_months > 60)
                                       ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..1.30 rows=1 width=129)
                                             Index Cond: (doc_id = child_health.awc_id)
                                             Filter: ((aggregation_level = 5) AND (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (district_is_test = 0) AND (child_health.supervisor_id = supervisor_id))
(20 rows)
*/



COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-10-01'
    )
WHERE child_health.age_in_months>36 and aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_Sept_3_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-10-01'
    )
WHERE child_health.age_in_months>60 and awc_location.aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_Sept_5_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0  AND
    awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=1 and lactating=0 and ccs_record.month = '2019-10-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name, month
) To '/tmp/thr_preg_Sept.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.supervisor_id, remote_scan.awc_name, remote_scan.month
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=5432 dbname=icds_ucr
               ->  GroupAggregate  (cost=106719.31..106719.47 rows=1 width=310)
                     Group Key: awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.supervisor_id, awc_location.awc_name, ccs_record.month
                     ->  Sort  (cost=106719.31..106719.32 rows=1 width=110)
                           Sort Key: awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.supervisor_id, awc_location.awc_name
                           ->  Gather  (cost=1000.55..106719.30 rows=1 width=110)
                                 Workers Planned: 5
                                 ->  Nested Loop  (cost=0.55..105719.20 rows=1 width=110)
                                       ->  Parallel Seq Scan on ccs_record_monthly_102712 ccs_record  (cost=0.00..100622.41 rows=2083 width=78)
                                             Filter: ((pregnant = 1) AND (lactating = 0) AND (month = '2019-10-01'::date))
                                       ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..2.44 rows=1 width=129)
                                             Index Cond: (doc_id = ccs_record.awc_id)
                                             Filter: ((district_is_test = 0) AND (aggregation_level = 5) AND (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (ccs_record.supervisor_id = supervisor_id))
(19 rows)

*/


COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=0 and lactating=1 and ccs_record.month = '2019-10-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_lact_Sept.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY (
select district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(thr_eligible) as thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END) as child_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_0,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END) as child_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_1_7,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)as  child_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_8_14,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)as child_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_15_21,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END) as child_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-10-01'
    )
WHERE thr_eligible=1 and awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_child_July.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.supervisor_id, remote_scan.awc_name, remote_scan.month
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=5432 dbname=icds_ucr
               ->  GroupAggregate  (cost=455173.05..455173.18 rows=1 width=310)
                     Group Key: awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.supervisor_id, awc_location.awc_name, child_health.month
                     ->  Sort  (cost=455173.05..455173.05 rows=1 width=110)
                           Sort Key: awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.supervisor_id, awc_location.awc_name
                           ->  Gather  (cost=1001.11..455173.04 rows=1 width=110)
                                 Workers Planned: 5
                                 ->  Nested Loop  (cost=1.11..454172.94 rows=1 width=110)
                                       ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..411985.61 rows=41400 width=78)
                                             Index Cond: (month = '2019-10-01'::date)
                                             Filter: (thr_eligible = 1)
                                       ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..1.01 rows=1 width=129)
                                             Index Cond: (doc_id = child_health.awc_id)
                                             Filter: ((aggregation_level = 5) AND (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (district_is_test = 0) AND (child_health.supervisor_id = supervisor_id))
(20 rows)
*/



COPY(select district_name, block_name,supervisor_name,awc_name,
cbe_table.cbe_conducted
FROM awc_location_local awc_location
LEFT JOIN (
                        select awc_id,
                               count(*) as cbe_conducted from
                            "ucr_icds-cas_static-cbe_form_f7988a04"
                                WHERE date_cbe_organise>='2019-10-01' and date_cbe_organise<'2019-11-01'
                                GROUP BY awc_id
                        ) cbe_table on  awc_location.doc_id = cbe_table.awc_id
WHERE awc_location.aggregation_level = 5 and awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039'

)To '/tmp/cbe_conduction.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
 Gather  (cost=47400.10..197120.62 rows=55578 width=74)
   Workers Planned: 4
   ->  Merge Left Join  (cost=46400.10..190562.82 rows=13894 width=74)
         Merge Cond: (awc_location.doc_id = "ucr_icds-cas_static-cbe_form_f7988a04".awc_id)
         ->  Sort  (cost=46399.67..46434.41 rows=13894 width=97)
               Sort Key: awc_location.doc_id
               ->  Parallel Bitmap Heap Scan on awc_location_local awc_location  (cost=2928.41..45443.61 rows=13894 width=97)
                     Recheck Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
                     Filter: (aggregation_level = 5)
                     ->  Bitmap Index Scan on awc_location_local_state_id_idx  (cost=0.00..2914.52 rows=57942 width=0)
                           Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
         ->  GroupAggregate  (cost=0.43..141406.63 rows=211011 width=41)
               Group Key: "ucr_icds-cas_static-cbe_form_f7988a04".awc_id
               ->  Index Scan using "ix_ucr_icds-cas_static-cbe_form_f7988a04_awc_id" on "ucr_icds-cas_static-cbe_form_f7988a04"  (cost=0.43..136808.60 rows=497584 width=33)
                     Filter: ((date_cbe_organise >= '2019-10-01'::date) AND (date_cbe_organise < '2019-11-01'::date))
(15 rows)
*/
