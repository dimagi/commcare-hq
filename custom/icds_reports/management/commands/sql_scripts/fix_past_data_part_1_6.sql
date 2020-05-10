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
      district_id, 
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
          DISTINCT ucr.block_id
        FROM 
          "awc_location_local" ucr 
        WHERE 
          ucr.block_is_test = 0
          AND aggregation_level = 3
      ) tt ON tt.block_id = agg_child.block_id
    WHERE agg_child.aggregation_level=3
    GROUP BY 
      state_id, 
      district_id, 
      gender, 
      age_tranche
) ut 
WHERE 
  agg_child_health.district_id = ut.district_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche
  AND agg_child_health.aggregation_level=2;

--  QUERY PLAN
-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2017-03-01" agg_child_health  (cost=202452.77..202705.68 rows=16 width=550)
--    ->  Merge Join  (cost=202452.77..202705.68 rows=16 width=550)
--          Merge Cond: ((ut.district_id = agg_child_health.district_id) AND (ut.gender = agg_child_health.gender) AND (ut.age_tranche = agg_child_health.age_tranche))
--          ->  Sort  (cost=105313.55..105342.90 rows=11742 width=222)
--                Sort Key: ut.district_id, ut.gender, ut.age_tranche
--                ->  Subquery Scan on ut  (cost=102191.00..103790.02 rows=11742 width=222)
--                      ->  GroupAggregate  (cost=102191.00..103672.60 rows=11742 width=132)
--                            Group Key: agg_child.state_id, agg_child.district_id, agg_child.gender, agg_child.age_tranche
--                            ->  Sort  (cost=102191.00..102295.93 rows=41975 width=100)
--                                  Sort Key: agg_child.state_id, agg_child.district_id, agg_child.gender, agg_child.age_tranche
--                                  ->  Hash Join  (cost=2245.12..97623.09 rows=41975 width=100)
--                                        Hash Cond: (agg_child.block_id = ucr.block_id)
--                                        ->  Seq Scan on "agg_child_health_2017-03-01" agg_child  (cost=0.00..95267.61 rows=41975 width=132)
--                                              Filter: (aggregation_level = 3)
--                                        ->  Hash  (cost=2211.31..2211.31 rows=2705 width=32)
--                                              ->  HashAggregate  (cost=2157.21..2184.26 rows=2705 width=32)
--                                                    Group Key: ucr.block_id
--                                                    ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local ucr  (cost=0.42..2146.29 rows=4367 width=32)
--                                                          Index Cond: (aggregation_level = 3)
--                                                          Filter: (block_is_test = 0)
--          ->  Materialize  (cost=97139.22..97193.22 rows=10801 width=395)
--                ->  Sort  (cost=97139.22..97166.22 rows=10801 width=395)
--                      Sort Key: agg_child_health.district_id, agg_child_health.gender, agg_child_health.age_tranche
--                      ->  Seq Scan on "agg_child_health_2017-03-01" agg_child_health  (cost=0.00..95267.61 rows=10801 width=395)
--                            Filter: (aggregation_level = 2)
