UPDATE child_health_monthly
   SET
      height_measured_in_month = CASE
        WHEN (recorded_height is not NULL) AND (valid_in_month=1 AND age_tranche::Integer <= 60) THEN 1
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
    WHERE month='%(start_date)s';

-- QUERY PLAN
-- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Update on child_health_monthly_323196 child_health  (cost=1.12..5.61 rows=1 width=661)
--                Update on child_health_monthly_default_102648 child_health_1
--                ->  Nested Loop  (cost=1.12..5.61 rows=1 width=661)
--                      ->  Index Scan using icds_dashboard_growth_mo_month_state_id_9dfbeda1_idx_102264 on icds_dashboard_growth_monitoring_forms_102264 gm  (cost=0.56..2.77 rows=1 width=88)
--                            Index Cond: (month = '2017-03-01'::date)
--                      ->  Index Scan using child_health_monthly_default_102648_pkey on child_health_monthly_default_102648 child_health_1  (cost=0.56..2.78 rows=1 width=555)
--                            Index Cond: ((supervisor_id = gm.supervisor_id) AND (case_id = (gm.case_id)::text) AND (month = '2017-03-01'::date))
