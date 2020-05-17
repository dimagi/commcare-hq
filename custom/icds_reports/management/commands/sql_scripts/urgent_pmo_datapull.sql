select sum(pse_attended_21_days) as child_pse,sum(lunch_count_21_days) as child_hcm,sum(rations_21_plus_distributed) as child_thr, sum(weighed_and_height_measured_in_month) as height_weight_measured_in_month, sum(bf_at_birth) as bf_at_birth, sum(born_in_month) as born_in_month, sum(cf_initiation_in_month) as cf_initiation_in_month, sum(cf_initiation_eligible) as cf_initiation_eligible, sum(nutrition_status_weighed) as nutrition_status_weighed, sum(wasting_severe) as wasting_severe, sum(wasting_moderate) as wasting_moderate, sum(weighed_and_height_measured_in_month) as weighed_and_height_measured_in_month, sum(ebf_in_month) as ebf_in_month, sum(nutrition_status_moderately_underweight)+sum(nutrition_status_severely_underweight) as underweight_children, (sum(fully_immunized_on_time)+sum(fully_immunized_late))/sum(fully_immunized_eligible) as immunization, SUM(wer_eligible) as wer_eligible_child_health from "agg_child_health" where month='{month}' and aggregation_level=1 and state_is_test is distinct from 1;


/*
                                                       QUERY PLAN                                                        
-------------------------------------------------------------------------------------------------------------------------
 Aggregate  (cost=24.72..24.73 rows=1 width=24)
   ->  Append  (cost=0.00..23.54 rows=158 width=12)
         ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=12)
               Filter: ((state_is_test IS DISTINCT FROM 1) AND (month = '2018-09-01'::date) AND (aggregation_level = 1))
         ->  Seq Scan on "agg_child_health_2018-09-01_1"  (cost=0.00..22.75 rows=157 width=12)
               Filter: ((state_is_test IS DISTINCT FROM 1) AND (month = '2018-09-01'::date) AND (aggregation_level = 1))
(6 rows)

*/


select sum(rations_21_plus_distributed) as mother_thr,sum(valid_in_month) as pw_lw_enrolled, SUM(counsel_immediate_bf)/SUM(trimester_3) as counsel_immediatebf_isto_trimester_3 from agg_ccs_record where month='{month}' and aggregation_level=1 and state_is_test is distinct from 1;

/*
                                                       QUERY PLAN                                                        
-------------------------------------------------------------------------------------------------------------------------
 Aggregate  (cost=2.52..2.53 rows=1 width=8)
   ->  Append  (cost=0.00..2.52 rows=2 width=4)
         ->  Seq Scan on agg_ccs_record  (cost=0.00..0.00 rows=1 width=4)
               Filter: ((state_is_test IS DISTINCT FROM 1) AND (month = '2018-03-01'::date) AND (aggregation_level = 1))
         ->  Seq Scan on "agg_ccs_record_2018-03-01_1"  (cost=0.00..2.51 rows=1 width=4)
               Filter: ((state_is_test IS DISTINCT FROM 1) AND (month = '2018-03-01'::date) AND (aggregation_level = 1))
(6 rows)

*/


 select SUM(awc_days_open) as days_opened, sum(num_launched_awcs) as launched,SUM(awc_days_open)/sum(num_launched_awcs) as avg_days_opened,sum(cases_household) as total_household, sum(num_launched_states) as launched_states, sum(num_launched_districts) as launched_districts,sum(num_launched_blocks) as launched_blocks, sum(num_awcs_conducted_cbe) as num_awcs_conducted_cbe, sum(num_awcs_conducted_vhnd) as num_awcs_conducted_vhnd from agg_awc where month='{month}' and aggregation_level=1 and state_is_test is distinct from 1;

 /*
                                                        QUERY PLAN                                                        
-------------------------------------------------------------------------------------------------------------------------
 Aggregate  (cost=2.24..2.25 rows=1 width=24)
   ->  Append  (cost=0.00..2.22 rows=2 width=8)
         ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=8)
               Filter: ((state_is_test IS DISTINCT FROM 1) AND (month = '2018-03-01'::date) AND (aggregation_level = 1))
         ->  Seq Scan on "agg_awc_2018-03-01_1"  (cost=0.00..2.21 rows=1 width=8)
               Filter: ((state_is_test IS DISTINCT FROM 1) AND (month = '2018-03-01'::date) AND (aggregation_level = 1))
(6 rows)


 */



 select sum(CASE WHEN incentive_eligible THEN 1 ELSE 0 END ) as incentive_eligible, sum(CASE WHEN awh_eligible THEN 1 ELSE 0 END) as awh_eligible from icds_dashboard_aww_incentive where month='{month}' and is_launched=true;
 /*
 Finalize Aggregate  (cost=19316.33..19316.34 rows=1 width=16)
   ->  Gather  (cost=19315.90..19316.31 rows=4 width=16)
         Workers Planned: 4
         ->  Partial Aggregate  (cost=18315.90..18315.91 rows=1 width=16)
               ->  Parallel Append  (cost=0.00..17852.25 rows=92730 width=2)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_8048fca9e4eef64030deaa32  (cost=0.00..2787.88 rows=32710 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_44eedad853ea06ce7ff597aa  (cost=0.00..2714.99 rows=35279 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_574bb69e9c1384b0afd7a4bb  (cost=0.00..2571.68 rows=33014 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_50e93a769911a7e32580432d  (cost=0.00..2278.62 rows=29729 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_bcb4a507c13e764811865560  (cost=0.00..1361.54 rows=16363 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_f17ecdf7f4c62b67ccd3ffc6  (cost=0.00..1246.51 rows=15961 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_9328c152ea8a5dd8f402878a  (cost=0.00..1004.10 rows=12648 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_ad462e06e984977ee9a6f93d  (cost=0.00..919.57 rows=10925 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_f097d7fa3f9272bd1db105d5  (cost=0.00..549.27 rows=6582 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_c9fc6833563fe8049903a475  (cost=0.00..543.60 rows=6928 width=2)
                           Filter: (month = '2019-03-01'::date)
                     ->  Parallel Seq Scan on icds_db_aww_incentive_44c9a47a653b5bb720a56dcd  (cost=0.00..348.10 rows=4488 width=2)
 */

select sum(valid_in_month) as child_0_36 from "agg_child_health" where month='{month}' and age_tranche in ('6', '12', '24', '36') and aggregation_level=1;
select sum(valid_in_month) as child_36_72 from "agg_child_health" where month='{month}' and age_tranche in ('48', '60', '72') and aggregation_level=1;
select sum(valid_in_month) as child_72 from "agg_child_health" where month='{month}' and age_tranche::INTEGER <= 72  and aggregation_level=1;
select sum(valid_visits) as valid_visits, sum(expected_visits) as expected_visits,CASE WHEN sum(expected_visits)>0 THEN sum(valid_visits)/sum(expected_visits)::float*100 ELSE 0 END as exp_isto_valid,CASE WHEN sum(wer_eligible)>0 THEN sum(wer_weighed)/sum(wer_eligible)::float*100 ELSE 0 END as wer_eligble_isto_wer_weighed from "agg_awc" where month='{month}' and aggregation_level=1
