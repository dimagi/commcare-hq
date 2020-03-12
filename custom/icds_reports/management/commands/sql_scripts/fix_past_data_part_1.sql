UPDATE child_health_monthly child_health
   SET
      height_measured_in_month = CASE
        WHEN (gm.height_child_last_recorded >= '%(start_date)s' AND gm.height_child_last_recorded <'%(end_date)s') AND (valid_in_month=1 AND age_tranche::Integer <= 60) THEN 1
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
    AND child_health.month='%(start_date)s'
    AND gm.month='%(start_date)s'
    AND child_health.supervisor_id=gm.supervisor_id;