UPDATE 
  "agg_child_health_%(start_date)s_4" agg_child_health 
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
      ) as weighed_and_height_measured_in_month 
    FROM 
      "agg_child_health_%(start_date)s_5" agg_child 
      INNER JOIN (
        SELECT 
          DISTINCT ucr.doc_id 
        FROM 
          "awc_location_local" ucr 
        WHERE 
          ucr.awc_is_test = 0
          AND aggregation_level = 4
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