select SUM(CASE WHEN thr_eligible=1 THEN COALESCE(thr.days_ration_given_child, 0) ELSE 0 END)
from child_health_monthly inner join  awc_location ON (
      (child_health_monthly.supervisor_id = awc_location.supervisor_id) AND
      ("awc_location"."doc_id" = "child_health_monthly"."awc_id")
  )
left join icds_dashboard_child_health_thr_forms thr on
        (
        child_health_monthly.state_id= thr.state_id AND
        child_health_monthly.month = thr.month AND
        child_health_monthly.supervisor_id = thr.supervisor_id AND
        child_health_monthly.case_id = thr.case_id
        )
where child_health_monthly.month='2020-02-01' and state_is_test is distinct from 1

/* Aggregate  (cost=0.00..0.00 rows=0 width=0)
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=6432 dbname=icds_ucr
               ->  Finalize Aggregate  (cost=182115.73..182115.74 rows=1 width=8)
                     ->  Gather  (cost=182115.31..182115.72 rows=4 width=8)
                           Workers Planned: 4
                           ->  Partial Aggregate  (cost=181115.31..181115.32 rows=1 width=8)
                                 ->  Nested Loop Left Join  (cost=1.54..181115.23 rows=10 width=6)
                                       ->  Merge Join  (cost=0.99..181108.30 rows=10 width=111)
                                             Merge Cond: (awc_location.doc_id = child_health_monthly.awc_id)
                                             Join Filter: (child_health_monthly.supervisor_id = awc_location.supervisor_id)
                                             ->  Parallel Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..71626.29 rows=197665 width=63)
                                                   Filter: (state_is_test IS DISTINCT FROM 1)
                                             ->  Materialize  (cost=0.43..103229.79 rows=910057 width=144)
                                                   ->  Merge Append  (cost=0.43..100954.65 rows=910057 width=144)
                                                         Sort Key: child_health_monthly.awc_id
                                                         ->  Index Scan using "child_health_monthly_2020-02-01_512124_awc_id_idx" on "child_health_monthly_2020-02-01_512124" child_health_monthly  (cost=0.42..91854.07 rows=910057 width=144)
                                                               Filter: (month = '2020-02-01'::date)
                                       ->  Index Scan using icds_dashboard_child_health_thr_forms_pkey_102200 on icds_dashboard_child_health_thr_forms_102200 thr  (cost=0.55..0.68 rows=1 width=109)
                                             Index Cond: ((child_health_monthly.supervisor_id = supervisor_id) AND (child_health_monthly.case_id = (case_id)::text) AND (child_health_monthly.month = month) AND (month = '2020-02-01'::date))
                                             Filter: (child_health_monthly.state_id = (state_id)::text)
(24 rows)
*/
