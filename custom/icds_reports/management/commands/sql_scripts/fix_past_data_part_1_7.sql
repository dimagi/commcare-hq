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
      state_id, 
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
          DISTINCT ucr.district_id 
        FROM 
          "awc_location_local" ucr 
        WHERE 
          ucr.district_is_test = 0
          AND aggregation_level = 2
      ) tt ON tt.district_id = agg_child.district_id
    WHERE agg_child.aggregation_level=2
    GROUP BY 
      state_id, 
      gender, 
      age_tranche
  ) ut 
WHERE 
  agg_child_health.state_id = ut.state_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche
  AND agg_child_health.aggregation_level=1;


-- QUERY PLAN
-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2017-03-01" agg_child_health  (cost=96546.77..191831.08 rows=1 width=551)
--    ->  Hash Join  (cost=96546.77..191831.08 rows=1 width=551)
--          Hash Cond: ((agg_child_health.state_id = ut.state_id) AND (agg_child_health.gender = ut.gender) AND (agg_child_health.age_tranche = ut.age_tranche))
--          ->  Seq Scan on "agg_child_health_2017-03-01" agg_child_health  (cost=0.00..95267.61 rows=2118 width=395)
--                Filter: (aggregation_level = 1)
--          ->  Hash  (cost=96541.73..96541.73 rows=288 width=224)
--                ->  Subquery Scan on ut  (cost=96211.94..96541.73 rows=288 width=224)
--                      ->  GroupAggregate  (cost=96211.94..96538.85 rows=288 width=100)
--                            Group Key: agg_child.state_id, agg_child.gender, agg_child.age_tranche
--                            ->  Sort  (cost=96211.94..96238.94 rows=10801 width=68)
--                                  Sort Key: agg_child.state_id, agg_child.gender, agg_child.age_tranche
--                                  ->  Hash Join  (cost=191.87..95488.33 rows=10801 width=68)
--                                        Hash Cond: (agg_child.district_id = ucr.district_id)
--                                        ->  Seq Scan on "agg_child_health_2017-03-01" agg_child  (cost=0.00..95267.61 rows=10801 width=100)
--                                              Filter: (aggregation_level = 2)
--                                        ->  Hash  (cost=188.85..188.85 rows=241 width=32)
--                                              ->  HashAggregate  (cost=184.03..186.44 rows=241 width=32)
--                                                    Group Key: ucr.district_id
--                                                    ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local ucr  (cost=0.42..183.13 rows=362 width=32)
--                                                          Index Cond: (aggregation_level = 2)
--                                                          Filter: (district_is_test = 0)
