-- child health table fix
-- Needs to executed for each month
UPDATE child_health_monthly child_health
   SET
      height_measured_in_month = CASE
        WHEN (gm.height_child_last_recorded >= '2018-05-01' AND gm.height_child_last_recorded <'2018-06-01') AND (valid_in_month=1 AND age_tranche::Integer <= 60) THEN 1
        ELSE
          0
        END,
      current_month_stunting = CASE
        WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
        ELSE
            current_month_stunting
        END,
      stunting_last_recorded = CASE
        WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
        ELSE
           stunting_last_recorded
        END,
      wasting_last_recorded = CASE
        WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
       ELSE
          wasting_last_recorded
       END,
      current_month_wasting = CASE
        WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
        ELSE
          current_month_wasting
        END
   FROM icds_dashboard_growth_monitoring_forms gm
   WHERE child_health.case_id = gm.case_id
    AND child_health.month = gm.month
    AND child_health.month='2018-05-01'
    AND gm.month='2018-05-01'
    AND child_health.supervisor_id=gm.supervisor_id;


                                                                                         QUERY PLAN
-- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Update on child_health_monthly_323196 child_health  (cost=1.11..5.51 rows=1 width=661)
--                Update on child_health_monthly_default_102648 child_health_1
--                ->  Nested Loop  (cost=1.11..5.51 rows=1 width=661)
--                      ->  Index Scan using icds_dashboard_growth_mo_month_state_id_9dfbeda1_idx_102264 on icds_dashboard_growth_monitoring_forms_102264 gm  (cost=0.56..2.67 rows=1 width=88)
--                            Index Cond: (month = '2018-05-01'::date)
--                      ->  Index Scan using child_health_monthly_default_102648_pkey on child_health_monthly_default_102648 child_health_1  (cost=0.56..2.78 rows=1 width=555)
--                            Index Cond: ((supervisor_id = gm.supervisor_id) AND (case_id = (gm.case_id)::text) AND (month = '2018-05-01'::date))
-- (12 rows)

-- aggegrate child health table fix
DROP TABLE IF EXISTS temp_agg_child_my;
CREATE TABLE temp_agg_child_my AS 
SELECT 
  awc_id, 
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
  chm.month = '2018-05-01' 
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
-- cost 
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 -- Sort  (cost=0.00..0.00 rows=0 width=0)
 --   Sort Key: remote_scan.awc_id
 --   ->  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
 --         Group Key: remote_scan.awc_id, remote_scan.month, remote_scan.sex, remote_scan.age_tranche, remote_scan.caste, remote_scan.coalesce_disabled, remote_scan.coalesce_minority, remote_scan.coalesce_resident
 --         ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
 --               Task Count: 64
 --               Tasks Shown: One of 64
 --               ->  Task
 --                     Node: host=100.71.184.232 port=6432 dbname=icds_ucr
 --                     ->  Finalize GroupAggregate  (cost=148618.89..160818.19 rows=15011 width=205)
 --                           Group Key: chm.awc_id, chm.month, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
 --                           ->  Gather Merge  (cost=148618.89..158266.32 rows=60044 width=205)
 --                                 Workers Planned: 4
 --                                 ->  Partial GroupAggregate  (cost=147618.83..150114.44 rows=15011 width=205)
 --                                       Group Key: chm.awc_id, chm.month, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
 --                                       ->  Sort  (cost=147618.83..147712.65 rows=37528 width=167)
 --                                             Sort Key: chm.awc_id, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
 --                                             ->  Parallel Append  (cost=0.56..142963.52 rows=37528 width=167)
 --                                                   ->  Parallel Index Scan using chm_month_supervisor_id_default_102648 on child_health_monthly_default_102648 chm  (cost=0.56..142775.88 rows=37528 width=167)
 --                                                         Index Cond: (month = '2018-05-01'::date)



UPDATE "agg_child_health_2018-05-01_5" agg_child_health
  SET
    wasting_moderate = ut.wasting_moderate,
    wasting_severe = ut.wasting_severe,
    wasting_normal = ut.wasting_normal,
    stunting_moderate = ut.stunting_moderate,
    stunting_severe = ut.stunting_severe,
    stunting_normal = ut.stunting_normal,
    height_measured_in_month = ut.height_measured_in_month,
    weighed_and_height_measured_in_month = ut.weighed_and_height_measured_in_month
  FROM temp_agg_child_my AS ut
  WHERE (
    agg_child_health.awc_id=ut.awc_id and 
    agg_child_health.month=ut.month and
    agg_child_health.gender=ut.sex and
    agg_child_health.age_tranche=ut.age_tranche and
    agg_child_health.caste=ut.caste and
    agg_child_health.disabled=ut.coalesce_disabled and
    agg_child_health.minority = ut.coalesce_minority and
    agg_child_health.resident = ut.coalesce_resident
  )

Roll Ups:

UPDATE 
  "agg_child_health_2018-05-01_4" agg_child_health 
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
      "agg_child_health_2019-01-01_5" agg_child 
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



UPDATE 
  "agg_child_health_2018-05-01_3" agg_child_health 
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
      ) as weighed_and_height_measured_in_month 
    FROM 
      "agg_child_health_2018-05-01_4" agg_child 
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
  )
) ut 
WHERE 
  agg_child_health.block_id = ut.block_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche;


UPDATE 
  "agg_child_health_2018-05-01_2" agg_child_health 
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
      "agg_child_health_2018-05-01_3" agg_child 
      INNER JOIN (
        SELECT 
          DISTINCT ucr.supervisor_id 
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
  )
) ut 
WHERE 
  agg_child_health.district_id = ut.district_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche;


UPDATE 
  "agg_child_health_2018-05-01_1" agg_child_health 
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
      ) as weighed_and_height_measured_in_month 
    FROM 
      "agg_child_health_2018-05-01_2" agg_child 
      INNER JOIN (
        SELECT 
          DISTINCT ucr.district_id 
        FROM 
          "awc_location_local" ucr 
        WHERE 
          ucr.district_is_test = 0
          AND aggregation_level = 2
      ) tt ON tt.district_id = agg_child.district_id 
    GROUP BY 
      state_id, 
      gender, 
      age_tranche
  ) ut 
WHERE 
  agg_child_health.state_id = ut.state_id 
  AND agg_child_health.gender = ut.gender 
  AND agg_child_health.age_tranche = ut.age_tranche;

