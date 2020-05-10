UPDATE 
  "agg_child_health_{start_date}" agg_child_health
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
      "agg_child_health_{start_date}" agg_child
      INNER JOIN (
        SELECT 
          DISTINCT ucr.supervisor_id 
        FROM 
          "awc_location_local" ucr
        WHERE 
          ucr.supervisor_is_test = 0
          AND aggregation_level = 4
      ) tt ON tt.supervisor_id = agg_child.supervisor_id
    WHERE agg_child.aggregation_level=4
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
  AND agg_child_health.age_tranche = ut.age_tranche
  AND agg_child_health.aggregation_level=3;

-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2017-03-01" agg_child_health  (cost=272217.90..273715.30 rows=429 width=550)
--    ->  Merge Join  (cost=272217.90..273715.30 rows=429 width=550)
--          Merge Cond: ((ut.block_id = agg_child_health.block_id) AND (ut.gender = agg_child_health.gender) AND (ut.age_tranche = agg_child_health.age_tranche))
--          ->  Sort  (cost=164817.88..165057.84 rows=95985 width=222)
--                Sort Key: ut.block_id, ut.gender, ut.age_tranche
--                ->  Subquery Scan on ut  (cost=136992.33..144960.27 rows=95985 width=222)
--                      ->  GroupAggregate  (cost=136992.33..144000.42 rows=95985 width=164)
--                            Group Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.gender, agg_child.age_tranche
--                            ->  Sort  (cost=136992.33..137424.35 rows=172807 width=132)
--                                  Sort Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.gender, agg_child.age_tranche
--                                  ->  Hash Join  (cost=12396.21..108117.55 rows=172807 width=132)
--                                        Hash Cond: (agg_child.supervisor_id = ucr.supervisor_id)
--                                        ->  Seq Scan on "agg_child_health_2017-03-01" agg_child  (cost=0.00..95267.61 rows=172807 width=163)
--                                              Filter: (aggregation_level = 4)
--                                        ->  Hash  (cost=12183.20..12183.20 rows=17041 width=32)
--                                              ->  HashAggregate  (cost=11842.38..12012.79 rows=17041 width=32)
--                                                    Group Key: ucr.supervisor_id
--                                                    ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local ucr  (cost=0.42..11775.75 rows=26650 width=32)
--                                                          Index Cond: (aggregation_level = 4)
--                                                          Filter: (supervisor_is_test = 0)
--          ->  Materialize  (cost=107400.01..107609.89 rows=41975 width=395)
--                ->  Sort  (cost=107400.01..107504.95 rows=41975 width=395)
--                      Sort Key: agg_child_health.block_id, agg_child_health.gender, agg_child_health.age_tranche
--                      ->  Seq Scan on "agg_child_health_2017-03-01" agg_child_health  (cost=0.00..95267.61 rows=41975 width=395)
--                            Filter: (aggregation_level = 3)
