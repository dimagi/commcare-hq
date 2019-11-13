-- FETCH BY SUPERVISOR AND BRING TO MASTER, SIMILAR QUERY Needs to performed on CCS RECORD
create unlogged table temp_thr_data_pull as select
supervisor_id,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END) as child_thr_0,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>0 and num_rations_distributed<=7 then 1 ELSE 0 END) as child_thr_1_7,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)as  child_thr_8_14,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)as child_thr_15_21,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END) as child_thr_gt_21,
SUM(thr_eligible) as thr_eligible
from "child_health_monthly" child_health where month='2019-10-01'
group by supervisor_id;
​/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.supervisor_id
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=5432 dbname=icds_ucr
               ->  Finalize GroupAggregate  (cost=1000.64..417186.39 rows=306 width=81)
                     Group Key: supervisor_id
                     ->  Gather Merge  (cost=1000.64..417156.55 rows=1530 width=81)
                           Workers Planned: 5
                           ->  Partial GroupAggregate  (cost=0.56..415972.23 rows=306 width=81)
                                 Group Key: supervisor_id
                                 ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..411701.07 rows=113816 width=41)
                                       Index Cond: (month = '2019-10-01'::date)
(15 rows)

*/

create unlogged table temp_pse_data_pull as select
supervisor_id,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended=0 then 1 ELSE 0 END) as child_pse_0,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>0 and pse_days_attended<=7 then 1 ELSE 0 END) as child_pse_1_7,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>=8 and pse_days_attended<=14 then 1 ELSE 0 END)as  child_pse_8_14,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>=15 and pse_days_attended<=21 then 1 ELSE 0 END)as child_pse_15_21,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>21 then 1 ELSE 0 END) as child_pse_gt_21,
SUM(pse_eligible) as pse_eligible
from "child_health_monthly" child_health where month='2019-10-01' and age_tranche::INTEGER  BETWEEN 37 AND 72
group by supervisor_id;
/*
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.supervisor_id
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=5432 dbname=icds_ucr
               ->  Finalize GroupAggregate  (cost=1000.64..414646.87 rows=306 width=81)
                     Group Key: supervisor_id
                     ->  Gather Merge  (cost=1000.64..414617.03 rows=1530 width=81)
                           Workers Planned: 5
                           ->  Partial GroupAggregate  (cost=0.56..413432.71 rows=306 width=81)
                                 Group Key: supervisor_id
                                 ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..413408.31 rows=569 width=41)
                                       Index Cond: (month = '2019-10-01'::date)
                                       Filter: (((age_tranche)::integer >= 37) AND ((age_tranche)::integer <= 72))
(16 rows)
*/​




---- ROLLUP BY STATE
select
state_name,
sum(child_thr_0),
sum(child_thr_1_7),
sum(child_thr_8_14),
sum(child_thr_15_21),
sum( child_thr_gt_21),
sum(thr_eligible)
from temp_thr_data_pull t join awc_location_local a on a.supervisor_id=t.supervisor_id where aggregation_level=4 and state_is_test=0 group by state_name order by state_name asc;
​



select
state_name,
sum(child_pse_0),
sum(child_pse_1_7),
sum(child_pse_8_14),
sum(child_pse_15_21),
sum( child_pse_gt_21),
sum(pse_eligible)
from temp_pse_data_pull t join awc_location_local a on a.supervisor_id=t.supervisor_id where aggregation_level=4 and state_is_test=0 group by state_name order by state_name asc;







/*
Below is another approach. WE should decide which to take
*/

-- BELOW IS THE SECOND APPROACH WHICH CAN BE USED IS:


-- 1. Aggregate from child_health/ ccs record using chunking  by supervisor like thi

CREATE TEMPORARY TABLE dummy_thr_table_{} AS -- number of dummy_thr_table_{} tables will be equal to number of chunks(124)
(
select supervisor_id,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,
SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21
from
"ccs_record_monthly" ccs_record where (
    supervisor_id in ({}) AND
    thr_eligible=1 and ccs_record.month='2019-10-01'
    )
group by  supervisor_id);
/*
Approx cost of each chunk
HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.supervisor_id
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 59
         Tasks Shown: One of 59
         ->  Task
               Node: host=100.71.184.229 port=5432 dbname=icds_ucr
               ->  GroupAggregate  (cost=0.55..3326.07 rows=262 width=81)
                     Group Key: supervisor_id
                     ->  Index Scan using ccs_record_monthly_pkey_102754 on ccs_record_monthly_102754 ccs_record  (cost=0.55..3229.60 rows=1877 width=41)
                           Index Cond: ((supervisor_id = ANY ('{f9b47ea2ee2d8a02acddeeb491d3d1fd,f9b47ea2ee2d8a02acddeeb491d2b373,f9b47ea2ee2d8a02acddeeb491d1de8a,f9b47ea2ee2d8a02acddeeb491d0d0ab,f9b47ea2ee2d8a02acdde
*/





-- 2. INSERT INTO master table from chunked tables
INSERT INTO dummy_thr_tablex(supervisor_id,mother_thr_eligible, mother_thr_0,mother_thr_1_7,mother_thr_8_14,mother_thr_15_21,mother_thr_gt_21) (
    select supervisor_id,mother_thr_eligible, mother_thr_0,mother_thr_1_7,mother_thr_8_14,mother_thr_15_21,mother_thr_gt_21
    from dummy_thr_table_{}
    );



-- 3. Aggregate to state from supervisor.


