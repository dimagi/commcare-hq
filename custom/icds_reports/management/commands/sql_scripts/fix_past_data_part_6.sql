UPDATE 
  "agg_child_health_{start_date}_2" agg_child_health
SET 
  lunch_count_21_days = ut.lunch_count_21_days
FROM 
  (
    SELECT 
      district_id, 
      gender, 
      age_tranche, 
      SUM(lunch_count_21_days) as lunch_count_21_days
    FROM 
      "agg_child_health_{start_date}_3" agg_child
      INNER JOIN (
        SELECT 
          DISTINCT ucr.block_id
        FROM 
          "awc_location_local" ucr 
        WHERE 
          ucr.block_is_test = 0
          AND aggregation_level = 3
      ) tt ON tt.block_id = agg_child.block_id 
    GROUP BY 
      state_id, 
      district_id, 
      gender, 
      age_tranche
) ut 
WHERE 
  agg_child_health.district_id = ut.district_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche;
