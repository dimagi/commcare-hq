select sum(pse_attended_21_days) as child_pse,sum(lunch_count_21_days) as child_hcm,sum(rations_21_plus_distributed) as child_thr, sum(weighed_and_height_measured_in_month) as height_weight_measured_in_month from "agg_child_health" where month='2018-03-01' and aggregation_level=1 and state_is_test is distinct from 1 and state_id in ('f98e91aa003accb7b849a0f18ebd7039','f9b47ea2ee2d8a02acddeeb491d3e175','a2fcb186e9be8464e167bb1c56ce8fd9','f1cd643f0df908421abd915298ba57bc', '2af81d10b2ca4229a54bab97a5150538','d982a6fb4cca0824fbde59db18d3800f','9cd4fd88d9f047088a377b7e7d144830','9051ef4f91d54a89b89c533780857e05');


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


select sum(rations_21_plus_distributed) as mother_thr,sum(valid_in_month) as pw_lw_enrolled from agg_ccs_record where month='2018-03-01' and aggregation_level=1 and state_is_test is distinct from 1 and state_id in ('f98e91aa003accb7b849a0f18ebd7039','f9b47ea2ee2d8a02acddeeb491d3e175','a2fcb186e9be8464e167bb1c56ce8fd9','f1cd643f0df908421abd915298ba57bc', '2af81d10b2ca4229a54bab97a5150538','d982a6fb4cca0824fbde59db18d3800f','9cd4fd88d9f047088a377b7e7d144830','9051ef4f91d54a89b89c533780857e05');

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


 select SUM(awc_days_open) as days_opened, sum(num_launched_awcs) as launched,SUM(awc_days_open)/sum(num_launched_awcs) as avg_days_opened,sum(cases_household) as total_household, sum(num_launched_states) as launched_states, sum(num_launched_districts) as launched_districts,sum(num_launched_blocks) as launched_blocks from agg_awc where month='2018-03-01' and aggregation_level=1 and state_is_test is distinct from 1 and state_id in ('f98e91aa003accb7b849a0f18ebd7039','f9b47ea2ee2d8a02acddeeb491d3e175','a2fcb186e9be8464e167bb1c56ce8fd9','f1cd643f0df908421abd915298ba57bc', '2af81d10b2ca4229a54bab97a5150538','d982a6fb4cca0824fbde59db18d3800f','9cd4fd88d9f047088a377b7e7d144830','9051ef4f91d54a89b89c533780857e05');

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



 select sum(CASE WHEN incentive_eligible THEN 1 ELSE 0 END ), sum(CASE WHEN awh_eligible THEN 1 ELSE 0 END) from icds_dashboard_aww_incentive where month='2019-03-01' and is_launched=true and state_id in ('f98e91aa003accb7b849a0f18ebd7039','f9b47ea2ee2d8a02acddeeb491d3e175','a2fcb186e9be8464e167bb1c56ce8fd9','f1cd643f0df908421abd915298ba57bc', '2af81d10b2ca4229a54bab97a5150538','d982a6fb4cca0824fbde59db18d3800f','9cd4fd88d9f047088a377b7e7d144830','9051ef4f91d54a89b89c533780857e05');
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

select sum(valid_in_month) from "agg_child_health" where month='2018-03-01' and age_tranche in ('6', '12', '24', '36') and aggregation_level=1 and state_id in ('f98e91aa003accb7b849a0f18ebd7039','f9b47ea2ee2d8a02acddeeb491d3e175','a2fcb186e9be8464e167bb1c56ce8fd9','f1cd643f0df908421abd915298ba57bc', '2af81d10b2ca4229a54bab97a5150538','d982a6fb4cca0824fbde59db18d3800f','9cd4fd88d9f047088a377b7e7d144830','9051ef4f91d54a89b89c533780857e05');;
select sum(valid_in_month) from "agg_child_health" where month='2018-03-01' and age_tranche in ('48', '60', '72') and aggregation_level=1 and state_id in ('f98e91aa003accb7b849a0f18ebd7039','f9b47ea2ee2d8a02acddeeb491d3e175','a2fcb186e9be8464e167bb1c56ce8fd9','f1cd643f0df908421abd915298ba57bc', '2af81d10b2ca4229a54bab97a5150538','d982a6fb4cca0824fbde59db18d3800f','9cd4fd88d9f047088a377b7e7d144830','9051ef4f91d54a89b89c533780857e05');;
select sum(valid_in_month) from "agg_child_health" where month='2018-03-01' and age_tranche::INTEGER <= 72  and aggregation_level=1 and state_id in ('f98e91aa003accb7b849a0f18ebd7039','f9b47ea2ee2d8a02acddeeb491d3e175','a2fcb186e9be8464e167bb1c56ce8fd9','f1cd643f0df908421abd915298ba57bc', '2af81d10b2ca4229a54bab97a5150538','d982a6fb4cca0824fbde59db18d3800f','9cd4fd88d9f047088a377b7e7d144830','9051ef4f91d54a89b89c533780857e05');;
select sum(valid_visits), sum(expected_visits),CASE WHEN sum(expected_visits)>0 THEN sum(valid_visits)/sum(expected_visits)::float*100 ELSE 0 END,CASE WHEN sum(wer_eligible)>0 THEN sum(wer_weighed)/sum(wer_eligible)::float*100 ELSE 0 END from "agg_awc" where month='2018-03-01' and aggregation_level=1 and state_id in ('f98e91aa003accb7b849a0f18ebd7039','f9b47ea2ee2d8a02acddeeb491d3e175','a2fcb186e9be8464e167bb1c56ce8fd9','f1cd643f0df908421abd915298ba57bc', '2af81d10b2ca4229a54bab97a5150538','d982a6fb4cca0824fbde59db18d3800f','9cd4fd88d9f047088a377b7e7d144830','9051ef4f91d54a89b89c533780857e05');
