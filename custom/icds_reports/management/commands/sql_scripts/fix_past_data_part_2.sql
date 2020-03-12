DROP TABLE IF EXISTS temp_agg_child_my;
CREATE TABLE temp_agg_child_my AS 
SELECT 
  awc_id,
  supervisor_id, 
  chm.month, 
  sex, 
  age_tranche, 
  caste, 
  SUM(
    CASE WHEN chm.current_month_wasting = 'moderate' THEN 1 ELSE 0 END
  ) as wasting_moderate, 
  SUM(
    CASE WHEN chm.current_month_wasting = 'severe' THEN 1 ELSE 0 END
  ) as wasting_severe, 
  SUM(
    CASE WHEN chm.current_month_wasting = 'normal' THEN 1 ELSE 0 END
  ) as wasting_normal, 
  SUM(
    CASE WHEN chm.current_month_stunting = 'moderate' THEN 1 ELSE 0 END
  ) as stunting_moderate, 
  SUM(
    CASE WHEN chm.current_month_stunting = 'severe' THEN 1 ELSE 0 END
  ) as stunting_severe,
  SUM(
    CASE WHEN chm.current_month_stunting = 'normal' THEN 1 ELSE 0 END
  ) as stunting_normal, 
  SUM(chm.height_measured_in_month) as height_measured_in_month, 
  SUM(
    CASE WHEN chm.nutrition_status_weighed = 1 
    AND chm.height_measured_in_month = 1 THEN 1 ELSE 0 END
  ) as weighed_and_height_measured_in_month, 
  COALESCE(chm.disabled, 'no') as coalesce_disabled, 
  COALESCE(chm.minority, 'no') as coalesce_minority, 
  COALESCE(chm.resident, 'no') as coalesce_resident 
FROM 
  "child_health_monthly" chm 
WHERE 
  chm.month = '%(start_date)s' 
GROUP BY 
  chm.awc_id,
  chm.supervisor_id, 
  chm.month, 
  chm.sex, 
  chm.age_tranche, 
  chm.caste, 
  coalesce_disabled, 
  coalesce_minority, 
  coalesce_resident 
ORDER BY 
  chm.awc_id;