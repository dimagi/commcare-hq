SELECT COUNT(DISTINCT awc_id) FROM "ucr_icds-cas_static-usage_forms_92fbe2aa" WHERE form_time BETWEEN '2019-01-01' AND '2019-06-30';

/*
 Aggregate  (cost=0.00..0.00 rows=0 width=0)
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=6432 dbname=icds_ucr
               ->  Group  (cost=736115.96..742602.73 rows=8687 width=33)
                     Group Key: awc_id
                     ->  Gather Merge  (cost=736115.96..742472.42 rows=52122 width=33)
                           Workers Planned: 6
                           ->  Sort  (cost=735115.87..735137.58 rows=8687 width=33)
                                 Sort Key: awc_id
                                 ->  Partial HashAggregate  (cost=734460.67..734547.54 rows=8687 width=33)
                                       Group Key: awc_id
                                       ->  Parallel Seq Scan on "ucr_icds-cas_static-usage_forms_92fbe2aa_104250" "ucr_icds-cas_static-usage_forms_92fbe2aa"  (cost=0.00..732702.86 rows=703121 width=33)
                                             Filter: ((form_time >= '2019-01-01 00:00:00'::timestamp without time zone) AND (form_time <= '2019-06-30 00:00:00'::timestamp without time zone))
(16 rows)
*/


