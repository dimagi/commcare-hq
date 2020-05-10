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
      "agg_child_health_{start_date}" agg_child
      INNER JOIN (
        SELECT 
          DISTINCT ucr.doc_id 
        FROM 
          "awc_location_local" ucr 
        WHERE 
          ucr.awc_is_test = 0
          AND aggregation_level = 5
      ) tt ON tt.doc_id = agg_child.awc_id
    WHERE agg_child.aggregation_level=5
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
  AND agg_child_health.age_tranche = ut.age_tranche
  AND agg_child_health.aggregation_level=4;

-- QUERY PLAN
-- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2017-03-01" agg_child_health  (cost=801866.55..805142.68 rows=303 width=549)
--    ->  Merge Join  (cost=801866.55..805142.68 rows=303 width=549)
--          Merge Cond: ((agg_child_health.supervisor_id = ut.supervisor_id) AND (agg_child_health.gender = ut.gender) AND (agg_child_health.age_tranche = ut.age_tranche))
--          ->  Sort  (cost=146975.29..147407.30 rows=172807 width=395)
--                Sort Key: agg_child_health.supervisor_id, agg_child_health.gender, agg_child_health.age_tranche
--                ->  Seq Scan on "agg_child_health_2017-03-01" agg_child_health  (cost=0.00..95267.61 rows=172807 width=395)
--                      Filter: (aggregation_level = 4)
--          ->  Materialize  (cost=654891.27..655506.85 rows=123117 width=220)
--                ->  Sort  (cost=654891.27..655199.06 rows=123117 width=220)
--                      Sort Key: ut.supervisor_id, ut.gender, ut.age_tranche
--                      ->  Subquery Scan on ut  (cost=589104.74..629197.13 rows=123117 width=220)
--                            ->  GroupAggregate  (cost=589104.74..627965.96 rows=123117 width=195)
--                                  Group Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.supervisor_id, agg_child.gender, agg_child.age_tranche
--                                  ->  Sort  (cost=589104.74..591613.41 rows=1003468 width=163)
--                                        Sort Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.supervisor_id, agg_child.gender, agg_child.age_tranche
--                                        ->  Hash Join  (cost=189409.63..344434.37 rows=1003468 width=163)
--                                              Hash Cond: (agg_child.awc_id = ucr.doc_id)
--                                              ->  Seq Scan on "agg_child_health_2017-03-01" agg_child  (cost=0.00..95267.61 rows=1003468 width=190)
--                                                    Filter: (aggregation_level = 5)
--                                              ->  Hash  (cost=177515.61..177515.61 rows=615122 width=31)
--                                                    ->  Unique  (cost=0.55..171364.39 rows=615122 width=31)
--                                                          ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local ucr  (cost=0.55..169529.93 rows=733782 width=31)
--                                                                Filter: ((awc_is_test = 0) AND (aggregation_level = 5))
