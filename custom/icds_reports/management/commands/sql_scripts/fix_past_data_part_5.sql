UPDATE 
  "agg_child_health_{start_date}_3" agg_child_health
SET 
  wasting_moderate = ut.wasting_moderate, 
  wasting_severe = ut.wasting_severe, 
  wasting_normal = ut.wasting_normal, 
  stunting_moderate = ut.stunting_moderate, 
  stunting_severe = ut.stunting_severe, 
  stunting_normal = ut.stunting_normal, 
  height_measured_in_month = ut.height_measured_in_month, 
  weighed_and_height_measured_in_month = ut.weighed_and_height_measured_in_month,
  height_eligible = ut.height_eligible
FROM 
  (
    SELECT 
      block_id, 
      gender, 
      age_tranche, 
      SUM(wasting_moderate) as wasting_moderate, 
      SUM(wasting_severe) as wasting_severe, 
      SUM(wasting_normal) as wasting_normal, 
      SUM(stunting_moderate) as stunting_moderate, 
      SUM(stunting_severe) as stunting_severe, 
      SUM(stunting_normal) as stunting_normal, 
      SUM(height_measured_in_month) as height_measured_in_month, 
      SUM(
        weighed_and_height_measured_in_month
      ) as weighed_and_height_measured_in_month,
      SUM(height_eligible) as height_eligible
    FROM 
      "agg_child_health_{start_date}_4" agg_child
      INNER JOIN (
        SELECT 
          DISTINCT ucr.supervisor_id 
        FROM 
          "awc_location_local" ucr
        WHERE 
          ucr.supervisor_is_test = 0
          AND aggregation_level = 4
      ) tt ON tt.supervisor_id = agg_child.supervisor_id 
    GROUP BY 
      state_id, 
      district_id, 
      block_id, 
      gender, 
      age_tranche
) ut 
WHERE 
  agg_child_health.block_id = ut.block_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche;


--  QUERY PLAN
-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2017-05-01_3" agg_child_health  (cost=18969.11..20186.23 rows=3 width=506)
--    ->  Hash Join  (cost=18969.11..20186.23 rows=3 width=506)
--          Hash Cond: ((ut.block_id = agg_child_health.block_id) AND (ut.gender = agg_child_health.gender) AND (ut.age_tranche = agg_child_health.age_tranche))
--          ->  Subquery Scan on ut  (cost=18055.75..18151.15 rows=4770 width=224)
--                ->  HashAggregate  (cost=18055.75..18103.45 rows=4770 width=166)
--                      Group Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.gender, agg_child.age_tranche
--                      ->  Hash Join  (cost=12396.21..16505.47 rows=47701 width=134)
--                            Hash Cond: (agg_child.supervisor_id = ucr.supervisor_id)
--                            ->  Seq Scan on "agg_child_health_2017-05-01_4" agg_child  (cost=0.00..3984.01 rows=47701 width=167)
--                            ->  Hash  (cost=12183.20..12183.20 rows=17041 width=32)
--                                  ->  HashAggregate  (cost=11842.38..12012.79 rows=17041 width=32)
--                                        Group Key: ucr.supervisor_id
--                                        ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local ucr  (cost=0.42..11775.75 rows=26650 width=32)
--                                              Index Cond: (aggregation_level = 4)
--                                              Filter: (supervisor_is_test = 0)
--          ->  Hash  (cost=506.13..506.13 rows=6413 width=350)
--                ->  Seq Scan on "agg_child_health_2017-05-01_3" agg_child_health  (cost=0.00..506.13 rows=6413 width=350)
