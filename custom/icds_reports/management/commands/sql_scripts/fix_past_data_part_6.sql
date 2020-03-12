UPDATE 
  "agg_child_health_%(start_date)s_2" agg_child_health 
SET 
  wasting_moderate = ut.wasting_moderate, 
  wasting_severe = ut.wasting_severe, 
  wasting_normal = ut.wasting_normal, 
  stunting_moderate = ut.stunting_moderate, 
  stunting_severe = ut.stunting_severe, 
  stunting_normal = ut.stunting_normal, 
  height_measured_in_month = ut.height_measured_in_month, 
  weighed_and_height_measured_in_month = ut.weighed_and_height_measured_in_month 
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
      ) as weighed_and_height_measured_in_month 
    FROM 
      "agg_child_health_%(start_date)s_3" agg_child 
      INNER JOIN (
        SELECT 
          DISTINCT ucr.supervisor_id 
        FROM 
          "awc_location_local" ucr 
        WHERE 
          ucr.block_is_test = 0
          AND aggregation_level = 2
      ) tt ON tt.block_id = agg_child.block_id 
    GROUP BY 
      state_id, 
      district_id, 
      gender, 
      age_tranche
  )
) ut 
WHERE 
  agg_child_health.district_id = ut.district_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche;