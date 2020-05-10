UPDATE 
  "agg_child_health_{start_date}_4" agg_child_health
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
      supervisor_id, 
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
      "agg_child_health_{start_date}_5" agg_child
      INNER JOIN (
        SELECT 
          DISTINCT ucr.doc_id 
        FROM 
          "awc_location_local" ucr 
        WHERE 
          ucr.awc_is_test = 0
          AND aggregation_level = 5
      ) tt ON tt.doc_id = agg_child.awc_id 
    GROUP BY 
      state_id, 
      district_id, 
      block_id, 
      supervisor_id, 
      gender, 
      age_tranche
  ) ut 
WHERE 
  agg_child_health.supervisor_id = ut.supervisor_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche;


--   QUERY PLAN
-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2017-05-01_4" agg_child_health  (cost=1041859.10..1165412.53 rows=120 width=536)
--    ->  Hash Join  (cost=1041859.10..1165412.53 rows=120 width=536)
--          Hash Cond: ((ut.supervisor_id = agg_child_health.supervisor_id) AND (ut.gender = agg_child_health.gender) AND (ut.age_tranche = agg_child_health.age_tranche))
--          ->  Subquery Scan on ut  (cost=1034664.32..1118634.57 rows=212583 width=226)
--                ->  GroupAggregate  (cost=1034664.32..1116508.74 rows=212583 width=200)
--                      Group Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.supervisor_id, agg_child.gender, agg_child.age_tranche
--                      ->  Sort  (cost=1034664.32..1039978.89 rows=2125829 width=168)
--                            Sort Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.supervisor_id, agg_child.gender, agg_child.age_tranche
--                            ->  Hash Join  (cost=189409.63..504820.26 rows=2125829 width=168)
--                                  Hash Cond: (agg_child.awc_id = ucr.doc_id)
--                                  ->  Seq Scan on "agg_child_health_2017-05-01_5" agg_child  (cost=0.00..185215.29 rows=2125829 width=201)
--                                  ->  Hash  (cost=177515.61..177515.61 rows=615122 width=31)
--                                        ->  Unique  (cost=0.55..171364.39 rows=615122 width=31)
--                                              ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local ucr  (cost=0.55..169529.93 rows=733782 width=31)
--                                                    Filter: ((awc_is_test = 0) AND (aggregation_level = 5))
--          ->  Hash  (cost=3984.01..3984.01 rows=47701 width=379)
--                ->  Seq Scan on "agg_child_health_2017-05-01_4" agg_child_health  (cost=0.00..3984.01 rows=47701 width=379)
