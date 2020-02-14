-- child health table fix
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
UPDATE agg_child_health
 SET
     weighed_and_height_measured_in_month = tmp.weighed_and_height_measured_in_month,
     height_measured_in_month = tmp.height_measured_in_month,
     stunting_normal = tmp.stunting_normal,
     stunting_severe = tmp.stunting_severe,
     stunting_moderate = tmp.stunting_moderate,
     wasting_moderate = tmp.wasting_moderate,
     wasting_severe = tmp.wasting_severe,
     wasting_normal = tmp.wasting_normal
   FROM (
      SELECT
         chm.supervisor_id as supervisor_id,
         chm.awc_id as awc_id,
         chm.month as month,
         SUM(CASE WHEN chm.current_month_wasting = 'moderate' THEN 1 ELSE 0 END) as wasting_moderate,
         SUM(CASE WHEN chm.current_month_wasting = 'severe' THEN 1 ELSE 0 END) as wasting_severe,
         SUM(CASE WHEN chm.current_month_wasting = 'normal' THEN 1 ELSE 0 END) as wasting_normal,
         SUM(CASE WHEN chm.current_month_stunting = 'moderate' THEN 1 ELSE 0 END) as stunting_moderate,
         SUM(CASE WHEN chm.current_month_stunting = 'severe' THEN 1 ELSE 0 END) as stunting_severe,
         SUM(CASE WHEN chm.current_month_stunting = 'normal' THEN 1 ELSE 0 END) as stunting_normal,
         SUM(chm.height_measured_in_month) as height_measured_in_month,
         SUM(CASE WHEN chm.nutrition_status_weighed = 1 AND chm.height_measured_in_month = 1 THEN 1 ELSE 0 END) as weighed_and_height_measured_in_month

      FROM child_health_monthly chm
      WHERE chm.month = '2018-06-01'
            AND chm.supervisor_id >= '0'
            AND chm.supervisor_id < '1'
      GROUP BY chm.supervisor_id, chm.awc_id,
               chm.month, chm.sex, chm.age_tranche, chm.caste
   ) as tmp
   WHERE supervisor_id = tmp.supervisor_id
      AND awc_id = tmp.awc_id
      AND month = tmp.month
      AND aggregation_level = 5

