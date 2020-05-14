select sum(pse_attended_21_days) as child_pse,sum(lunch_count_21_days) as child_hcm,sum(rations_21_plus_distributed) as child_thr from "agg_child_health" where month='2018-03-01' and aggregation_level=1 and state_is_test is distinct from 1;


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


select sum(rations_21_plus_distributed) as mother_thr from agg_ccs_record where month='2018-03-01' and aggregation_level=1 and state_is_test is distinct from 1;

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


 select SUM(awc_days_open) as days_opened, sum(num_launched_awcs) as launched,SUM(awc_days_open)/sum(num_launched_awcs) as avg_days_opened from agg_awc where month='2018-03-01' and aggregation_level=1 and state_is_test is distinct from 1;

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