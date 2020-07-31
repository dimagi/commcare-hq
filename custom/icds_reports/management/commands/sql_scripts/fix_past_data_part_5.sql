UPDATE 
  "agg_child_health_{start_date}_3" agg_child_health
SET 
  lunch_count_21_days = ut.lunch_count_21_days
FROM 
  (
    SELECT 
      block_id, 
      gender, 
      age_tranche, 
      SUM(lunch_count_21_days) as lunch_count_21_days
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
