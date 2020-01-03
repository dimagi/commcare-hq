SELECT
district_name, age_tranche, sum(has_aadhar_id) AS "Adhaar Seeded", sum(valid_in_month) AS "Total"
FROM "public"."agg_child_health" "agg_child_health" 
RIGHT JOIN "public"."awc_location_months_local" "awc_location" 
ON awc_location.district_id=agg_child_health.district_id 
AND awc_location.supervisor_id=agg_child_health.supervisor_id
AND awc_location.aggregation_level=agg_child_health.aggregation_level
WHERE agg_child_health.month='2019-12-01' 
AND agg_child_health.state_id='2af81d10b2ca4229a54bab97a5150538'
AND agg_child_health.aggregation_level=2
GROUP BY age_tranche, district_name
ORDER BY district_name, age_tranche::INTEGER

/*
                                                                                            QUERY PLAN
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Sort  (cost=106.45..107.75 rows=520 width=46)
   Sort Key: awc_location.district_name, ((agg_child_health.age_tranche)::integer)
   ->  HashAggregate  (cost=75.19..82.99 rows=520 width=46)
         Group Key: agg_child_health.age_tranche, awc_location.district_name
         ->  Nested Loop  (cost=12.44..63.19 rows=1200 width=34)
               ->  Nested Loop  (cost=12.44..29.19 rows=1 width=34)
                     ->  Append  (cost=0.00..2.05 rows=2 width=94)
                           ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=108)
                                 Filter: ((aggregation_level = 2) AND (month = '2019-12-01'::date) AND (state_id = '2af81d10b2ca4229a54bab97a5150538'::text))
                           ->  Index Scan using staging_agg_child_health_aggregation_level_age_tranche_idx4 on "agg_child_health_2019-12-01" agg_child_health_1  (cost=0.44..2.04 rows=1 width=80)
                                 Index Cond: (aggregation_level = 2)
                                 Filter: ((month = '2019-12-01'::date) AND (state_id = '2af81d10b2ca4229a54bab97a5150538'::text))
                     ->  Bitmap Heap Scan on awc_location_local awc_location  (cost=12.44..13.56 rows=1 width=77)
                           Recheck Cond: ((supervisor_id = agg_child_health.supervisor_id) AND (aggregation_level = 2))
                           Filter: (agg_child_health.district_id = district_id)
                           ->  BitmapAnd  (cost=12.44..12.44 rows=1 width=0)
                                 ->  Bitmap Index Scan on awc_location_local_supervisor_id_idx  (cost=0.00..1.87 rows=29 width=0)
                                       Index Cond: (supervisor_id = agg_child_health.supervisor_id)
                                 ->  Bitmap Index Scan on awc_location_local_aggregation_level_idx  (cost=0.00..10.22 rows=426 width=0)
                                       Index Cond: (aggregation_level = 2)
               ->  Seq Scan on icds_months_local months  (cost=0.00..22.00 rows=1200 width=0)
(21 rows)
*/
