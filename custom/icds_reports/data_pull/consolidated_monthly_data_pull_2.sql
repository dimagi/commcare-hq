-- FETCH BY SUPERVISOR AND BRING TO MASTER, SIMILAR QUERY Needs to performed on CCS RECORD
DROP TABLE if EXISTS temp_thr_data_pull;
create unlogged table temp_thr_data_pull as select
supervisor_id,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END) as child_thr_0,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>0 and num_rations_distributed<=7 then 1 ELSE 0 END) as child_thr_1_7,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)as  child_thr_8_14,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)as child_thr_15_21,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END) as child_thr_gt_21,
SUM(thr_eligible) as thr_eligible
from "child_health_monthly" child_health where month='2019-12-01'
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
                                       Index Cond: (month = '2019-12-01'::date)
(15 rows)

*/

DROP TABLE if EXISTS temp_pse_data_pull;
create unlogged table temp_pse_data_pull as select
supervisor_id,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended=0 then 1 ELSE 0 END) as child_pse_0,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>0 and pse_days_attended<=7 then 1 ELSE 0 END) as child_pse_1_7,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>=8 and pse_days_attended<=14 then 1 ELSE 0 END)as  child_pse_8_14,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>=15 and pse_days_attended<=21 then 1 ELSE 0 END)as child_pse_15_21,
SUM(CASE WHEN pse_days_attended is not null and pse_days_attended>21 then 1 ELSE 0 END) as child_pse_gt_21,
SUM(pse_eligible) as pse_eligible
from "child_health_monthly" child_health where month='2019-12-01' and age_tranche::INTEGER  BETWEEN 37 AND 72
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
                                       Index Cond: (month = '2019-12-01'::date)
                                       Filter: (((age_tranche)::integer >= 37) AND ((age_tranche)::integer <= 72))
(16 rows)
*/​




---- ROLLUP BY STATE
COPY(
select
state_name,
sum(child_thr_0) as "# Children (6-36m) Given 0 Days THR",
sum(child_thr_1_7) as "# Children (6-36m) Given 1-7 Days THR",
sum(child_thr_8_14) as "# Children (6-36m) Given 8-14 Days THR",
sum(child_thr_15_21)as "# Children (6-36m) Given 15-21 Days THR",
sum( child_thr_gt_21) as "# Children (6-36m) Given >21 Days THR",
sum(thr_eligible) as "Total # of Children (6-36m) Eligible for THR"
from temp_thr_data_pull t join awc_location_local a on a.supervisor_id=t.supervisor_id
where aggregation_level=4 and state_is_test=0
group by state_name order by state_name ASC
) TO '/tmp/monthly_stats5.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(
select
state_name,
sum(child_pse_0) as "# Children (3-6y) who Attended PSE for 0 Days",
sum(child_pse_1_7) as "# Children (3-6y) who Attended PSE for 1-7 Days",
sum(child_pse_8_14)as "# Children (3-6y) who Attended PSE for 8-14 Days",
sum(child_pse_15_21) as "# Children (3-6y) who Attended PSE for 15-21 Days",
sum( child_pse_gt_21) as "# Children (3-6y) who Attended PSE for >21 Days",
sum(pse_eligible) as "Total Children (3-6y) Eligible to Attend PSE"
from temp_pse_data_pull t join awc_location_local a on a.supervisor_id=t.supervisor_id where aggregation_level=4 and state_is_test=0 group by state_name order by state_name asc
) TO '/tmp/monthly_stats6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';





-- BELOW IS similar query for ccs and then same rollup.
CREATE TEMPORARY TABLE dummy_thr_table AS
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
ccs_record.month='2019-12-01'
    )
group by  supervisor_id);


COPY(select
state_name,
sum(mother_thr_0) as "# PW and LM Given 0 Days THR",
sum(mother_thr_1_7) as "# PW and LM Given 1-7 Days THR",
sum(mother_thr_8_14) as "# PW and LM Given 8-14 Days THR",
sum(mother_thr_15_21) as "# PW and LM Given 15-21 Days THR",
sum( mother_thr_gt_21) as "# PW and LM Given >21 Days THR",
sum(mother_thr_eligible) as "Total # of PW and LM Eligible for THR"
from dummy_thr_table t join awc_location_local a on a.supervisor_id=t.supervisor_id where aggregation_level=4 and state_is_test=0 group by state_name order by state_name asc
) TO '/tmp/monthly_stats7.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

COPY(select
    state_name,
    sum(nutrition_status_moderately_underweight) + sum(nutrition_status_severely_underweight) as "# Underweight Children (0-5y)",
    sum(nutrition_status_weighed) as "Total Children (0-5y) Weighed",
    CASE WHEN sum(nutrition_status_weighed)>0 THEN trunc(((sum(nutrition_status_moderately_underweight) + sum(nutrition_status_severely_underweight))/sum(nutrition_status_weighed)::float*100)::numeric,2) ELSE 0 END "% Underweight Children (0-5y)",
    sum(zscore_grading_hfa_moderate) + sum(zscore_grading_hfa_severe) as "# Stunted Children (0-5y)",
    sum(zscore_grading_hfa_recorded_in_month) as "Total Children (0-5y) whose Height was Measured",
    CASE WHEN sum(zscore_grading_hfa_recorded_in_month)>0 THEN trunc(((sum(zscore_grading_hfa_moderate) + sum(zscore_grading_hfa_severe))/sum(zscore_grading_hfa_recorded_in_month)::float*100)::numeric,2) ELSE 0 END "% Children (0-5y) with Stunting",
    sum(wasting_moderate_v2) + sum(wasting_severe_v2) as "# Wasted Children (0-5y)",
    sum(zscore_grading_wfh_recorded_in_month) as "Total Children (0-5y) whose Height and Weight was Measured",
    CASE WHEN sum(zscore_grading_wfh_recorded_in_month)>0 THEN trunc(((sum(wasting_moderate_v2) + sum(wasting_severe_v2))/sum(zscore_grading_wfh_recorded_in_month)::float*100)::numeric,2) ELSE 0 END "% Children (0-5y) with Wasting"

from agg_child_health_monthly where month='2019-12-01' AND aggregation_level=1 and (age_tranche::integer<>72 OR age_tranche is null) group by state_name
) TO '/tmp/monthly_stats8.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
 HashAggregate  (cost=529.16..531.02 rows=24 width=154)
   Group Key: awc_location.state_name
   ->  Merge Left Join  (cost=504.32..516.34 rows=233 width=46)
         Merge Cond: ((awc_location.state_id = agg_child_health.state_id) AND (awc_location.district_id = agg_child_health.district_id) AND (awc_location.block_id = agg_child_health.block_id) AND (awc_location.supervisor_id = agg_child_health.supervisor_id) AND (awc_location.doc_id = agg_child_health.awc_id))
         Join Filter: ((months.start_date = agg_child_health.month) AND (awc_location.aggregation_level = agg_child_health.aggregation_level))
         Filter: (((agg_child_health.age_tranche)::integer <> 72) OR (agg_child_health.age_tranche IS NULL))
         ->  Sort  (cost=54.50..55.08 rows=234 width=178)
               Sort Key: awc_location.state_id, awc_location.district_id, awc_location.block_id, awc_location.supervisor_id, awc_location.doc_id
               ->  Nested Loop  (cost=0.42..45.29 rows=234 width=178)
                     ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..17.35 rows=39 width=174)
                           Index Cond: (aggregation_level = 1)
                     ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                           ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                                 Filter: (start_date = '2019-12-01'::date)
         ->  Sort  (cost=449.82..451.24 rows=566 width=207)
               Sort Key: agg_child_health.state_id, agg_child_health.district_id, agg_child_health.block_id, agg_child_health.supervisor_id, agg_child_health.awc_id
               ->  Append  (cost=0.00..423.94 rows=566 width=207)
                     ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=236)
                           Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1))
                     ->  Index Scan using staging_agg_child_health_aggregation_level_gender_idx2 on "agg_child_health_2019-12-01" agg_child_health_1  (cost=0.43..421.11 rows=565 width=207)
                           Index Cond: (aggregation_level = 1)
                           Filter: (month = '2019-12-01'::date)
(22 rows)

 */



COPY(select
    state_name,
    sum(low_birth_weight_in_month) as "# Newborns with Low Birth Weight",
    sum(weighed_and_born_in_month) as "Total Children Born and Weighed",
    CASE WHEN sum(weighed_and_born_in_month)>0 THEN trunc((sum(low_birth_weight_in_month)/sum(weighed_and_born_in_month)::float*100)::numeric,2) ELSE 0 END "% LBW",
    sum(bf_at_birth) as "# Children Breastfed at Birth",
    sum(born_in_month) as "Total Children Born",
    CASE WHEN sum(born_in_month)>0 THEN trunc((sum(bf_at_birth)/sum(born_in_month)::float*100)::numeric,2) ELSE 0 END "% EIBF",
    sum(ebf_in_month) as "# Children (0-6m) Exclusively Breastfed",
    sum(ebf_eligible) as "Total Children (0-6m)",
    CASE WHEN sum(ebf_eligible)>0 THEN trunc((sum(ebf_in_month)/sum(ebf_eligible)::float*100)::numeric,2) ELSE 0 END "% EBF",

    sum(nutrition_status_weighed) as "# Children (0-5y) Weighed",
    sum(wer_eligible) as "Total Children (0-5y) Eligible for Weighing",
    CASE WHEN sum(wer_eligible)>0 THEN trunc((sum(nutrition_status_weighed)/sum(wer_eligible)::float*100)::numeric,2) ELSE 0 END "Weighing Efficiency",
        sum(height_measured_in_month) as "# Children (6m-5y) whose Height was Measured",
    sum(height_eligible) as "Total Children (6m-5y) Eligible for Height Measurement",
    CASE WHEN sum(height_eligible)>0 THEN trunc((sum(height_measured_in_month)/sum(height_eligible)::float*100)::numeric,2) ELSE 0 END "Height Measurement Efficiency",
    sum(rations_21_plus_distributed) as "# Children (6-36) who got THR for at Least 21 Days",
    sum(thr_eligible) as "Total Children (6-36) Eligible for THR",
    CASE WHEN sum(thr_eligible)>0 THEN trunc((sum(rations_21_plus_distributed)/sum(thr_eligible)::float*100)::numeric,2) ELSE 0 END "% THR (6-36m, at Least 21 Days)",
    sum(cf_in_month) as "# Children Initiated on Appropriate Complementary Feeding",
    sum(cf_eligible) as "Total Children (6-24m)",
    CASE WHEN sum(cf_eligible)>0 THEN trunc((sum(cf_in_month)/sum(cf_eligible)::float*100)::numeric,2) ELSE 0 END "% CF"
from agg_child_health_monthly where month='2019-12-01' AND aggregation_level=1  group by state_name
) TO '/tmp/monthly_stats9.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

/*
HashAggregate  (cost=537.40..540.58 rows=24 width=346)
   Group Key: awc_location.state_name
   ->  Merge Left Join  (cost=504.32..516.34 rows=234 width=66)
         Merge Cond: ((awc_location.state_id = agg_child_health.state_id) AND (awc_location.district_id = agg_child_health.district_id) AND (awc_location.block_id = agg_child_health.block_id) AND (awc_location.supervisor_id = agg_child_health.supervisor_id) AND (awc_location.doc_id = agg_child_health.awc_id))
         Join Filter: ((months.start_date = agg_child_health.month) AND (awc_location.aggregation_level = agg_child_health.aggregation_level))
         ->  Sort  (cost=54.50..55.08 rows=234 width=178)
               Sort Key: awc_location.state_id, awc_location.district_id, awc_location.block_id, awc_location.supervisor_id, awc_location.doc_id
               ->  Nested Loop  (cost=0.42..45.29 rows=234 width=178)
                     ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..17.35 rows=39 width=174)
                           Index Cond: (aggregation_level = 1)
                     ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                           ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                                 Filter: (start_date = '2019-12-01'::date)
         ->  Sort  (cost=449.82..451.24 rows=566 width=225)
               Sort Key: agg_child_health.state_id, agg_child_health.district_id, agg_child_health.block_id, agg_child_health.supervisor_id, agg_child_health.awc_id
               ->  Append  (cost=0.00..423.94 rows=566 width=225)
                     ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=224)
                           Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1))
                     ->  Index Scan using staging_agg_child_health_aggregation_level_gender_idx2 on "agg_child_health_2019-12-01" agg_child_health_1  (cost=0.43..421.11 rows=565 width=225)
                           Index Cond: (aggregation_level = 1)
                           Filter: (month = '2019-12-01'::date)
(21 rows)

 */



COPY(select
    state_name,
    sum(institutional_delivery_in_month) as "# Institutional Deliveries",
    sum(delivered_in_month) as "Total Deliveries",
    CASE WHEN sum(delivered_in_month)>0 THEN trunc((sum(institutional_delivery_in_month)/sum(delivered_in_month)::float*100)::numeric, 2) ELSE 0 END as "% Institutional Deliveries",
    sum(rations_21_plus_distributed) as "# PW and LM Given Take Home Ration for at Least 21 Days",
    sum(thr_eligible) as "Total PW and LM Eligible for Take Home Ration",
    CASE WHEN sum(thr_eligible)>0 THEN trunc((sum(rations_21_plus_distributed)/sum(thr_eligible)::float*100)::numeric, 2) ELSE 0 END as "% THR (PW and LM, at Least 21 Days)"
from agg_ccs_record_monthly where aggregation_level=1 and month='2019-12-01' group by state_name
) TO '/tmp/monthly_stats10.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

/*
 HashAggregate  (cost=66.09..67.17 rows=24 width=106)
   Group Key: awc_location.state_name
   ->  Hash Left Join  (cost=8.64..59.65 rows=234 width=26)
         Hash Cond: ((months.start_date = agg_ccs_record.month) AND (awc_location.aggregation_level = agg_ccs_record.aggregation_level) AND (awc_location.state_id = agg_ccs_record.state_id) AND (awc_location.district_id = agg_ccs_record.district_id) AND (awc_location.block_id = agg_ccs_record.block_id) AND (awc_location.supervisor_id = agg_ccs_record.supervisor_id) AND (awc_location.doc_id = agg_ccs_record.awc_id))
         ->  Nested Loop  (cost=0.42..45.29 rows=234 width=178)
               ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..17.35 rows=39 width=174)
                     Index Cond: (aggregation_level = 1)
               ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                     ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-12-01'::date)
         ->  Hash  (cost=5.77..5.77 rows=89 width=74)
               ->  Append  (cost=0.00..5.77 rows=89 width=74)
                     ->  Seq Scan on agg_ccs_record  (cost=0.00..0.00 rows=1 width=184)
                           Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1))
                     ->  Seq Scan on "agg_ccs_record_2019-12-01_1" agg_ccs_record_1  (cost=0.00..5.32 rows=88 width=73)
                           Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1))
(16 rows)
 */




COPY(
    select
    state_name,
    total_thr_candidates as "Total Beneficiaries (PW, LM & Children 6-36m) Eligible for THR",
    thr_given_21_days as "#Beneficiaries (PW, LM & Children 6-36m) Given THR >=21 Days",
    CASE WHEN total_thr_candidates>0 THEN trunc((thr_given_21_days/total_thr_candidates::float*100)::numeric,2) ELSE 0 END as "% THR (PW, LM and Children 6-36m, at Least 21 Days)",

    pse_attended_21_days as "# Children (3-6y) who Attended PSE  >= 21 Days",
    children_3_6 as "Total Children (3-6y) Eligible to Attend PSE",
    CASE WHEN children_3_6>0 THEN trunc((pse_attended_21_days/children_3_6::float*100)::numeric, 2) ELSE 0 END as "% PSE (3-6y, at Least 21 Days)",

    lunch_count_21_days as "# Children (3-6y) Given Hot Cooked Meal for >=21 Days",
    children_3_6 as "Total Children (3-6y) Eligible for Hot Cooked Meal",
    CASE WHEN children_3_6>0 THEN trunc((lunch_count_21_days/children_3_6::float*100)::numeric, 2) ELSE 0 END as "% HCM (3-6y, at Least 21 Days)",

    expected_visits as "Total Expected Home Visits",
    valid_visits as "# Home Visits Done",
    CASE WHEN expected_visits>0 THEN trunc((valid_visits/expected_visits::float*100)::numeric,2) ELSE 0 END as "% HVs"

from service_delivery_monthly where aggregation_level=1 and month='2019-12-01'
) TO '/tmp/monthly_stats11.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
 Subquery Scan on service_delivery_monthly  (cost=49.86..50.02 rows=1 width=194)
   ->  GroupAggregate  (cost=49.86..49.94 rows=1 width=425)
         Group Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, agg_awc.month, agg_awc.num_launched_awcs, agg_awc.num_awcs_conducted_cbe, agg_awc.valid_visits, agg_awc.expected_visits, agg_awc.num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
         ->  Sort  (cost=49.86..49.87 rows=1 width=371)
               Sort Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, agg_awc.num_launched_awcs, agg_awc.num_awcs_conducted_cbe, agg_awc.valid_visits, agg_awc.expected_visits, agg_awc.num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
               ->  Nested Loop Left Join  (cost=8.19..49.85 rows=1 width=371)
                     Join Filter: ((agg_ccs_record.month = months.start_date) AND (agg_ccs_record.aggregation_level = awc_location.aggregation_level) AND (agg_ccs_record.state_id = awc_location.state_id) AND (agg_ccs_record.district_id = awc_location.district_id) AND (agg_ccs_record.block_id = awc_location.block_id) AND (agg_ccs_record.supervisor_id = awc_location.supervisor_id) AND (agg_ccs_record.awc_id = awc_location.doc_id))
                     ->  Nested Loop Left Join  (cost=0.42..37.86 rows=1 width=359)
                           Join Filter: (agg_child_health.month = months.start_date)
                           ->  Nested Loop  (cost=0.42..32.91 rows=1 width=337)
                                 ->  Nested Loop  (cost=0.42..7.85 rows=1 width=333)
                                       ->  Append  (cost=0.00..2.52 rows=2 width=188)
                                             ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=188)
                                                   Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1))
                                             ->  Seq Scan on "agg_awc_2019-12-01_1"  (cost=0.00..2.51 rows=1 width=188)
                                                   Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1))
                                       ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local awc_location  (cost=0.42..2.66 rows=1 width=309)
                                             Index Cond: (doc_id = agg_awc.awc_id)
                                             Filter: ((aggregation_level = 1) AND (agg_awc.state_id = state_id) AND (agg_awc.district_id = district_id) AND (agg_awc.block_id = block_id) AND (agg_awc.supervisor_id = supervisor_id))
                                 ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                                       Filter: (start_date = '2019-12-01'::date)
                           ->  Append  (cost=0.00..4.92 rows=2 width=191)
                                 ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=220)
                                       Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1) AND (aggregation_level = awc_location.aggregation_level) AND (state_id = awc_location.state_id) AND (district_id = awc_location.district_id) AND (block_id = awc_location.block_id) AND (supervisor_id = awc_location.supervisor_id) AND (awc_id = awc_location.doc_id))
                                 ->  Index Scan using staging_agg_child_health_aggregation_level_state_id_idx2 on "agg_child_health_2019-12-01"  (cost=0.56..4.91 rows=1 width=191)
                                       Index Cond: ((aggregation_level = awc_location.aggregation_level) AND (aggregation_level = 1) AND (state_id = awc_location.state_id))
                                       Filter: ((month = '2019-12-01'::date) AND (district_id = awc_location.district_id) AND (block_id = awc_location.block_id) AND (supervisor_id = awc_location.supervisor_id) AND (awc_id = awc_location.doc_id))
                     ->  HashAggregate  (cost=7.77..8.66 rows=89 width=73)
                           Group Key: agg_ccs_record.state_id, agg_ccs_record.district_id, agg_ccs_record.block_id, agg_ccs_record.supervisor_id, agg_ccs_record.awc_id, agg_ccs_record.aggregation_level, agg_ccs_record.month
                           ->  Append  (cost=0.00..5.77 rows=89 width=66)
                                 ->  Seq Scan on agg_ccs_record  (cost=0.00..0.00 rows=1 width=176)
                                       Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1))
                                 ->  Seq Scan on "agg_ccs_record_2019-12-01_1"  (cost=0.00..5.32 rows=88 width=65)
                                       Filter: ((month = '2019-12-01'::date) AND (aggregation_level = 1))
(34 rows)
 */

COPY(
select state_name,
sum(CASE WHEN age_tranche::INTEGER<=6 THEN valid_in_month ELSE 0 END ) as  "# Children (0-6m)",
sum(CASE WHEN age_tranche::INTEGER BETWEEN 7 and 36 THEN valid_in_month ELSE 0 END ) as "# Children (6m-3y)",
sum(CASE WHEN age_tranche::INTEGER>36 THEN valid_in_month ELSE 0 END ) as "# Children (3-6y)"
from "agg_child_health_monthly"
where month='2019-12-01' and aggregation_level=1
group by state_name order by state_name
) TO '/tmp/monthly_stats12.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
