UPDATE "agg_child_health_{start_date}" agg_child_health
  SET
    lunch_count_21_days = ut.lunch_count_21_days
  FROM temp_chm_local ut
  WHERE (
    agg_child_health.awc_id=ut.awc_id and
    agg_child_health.month=ut.month and
    agg_child_health.gender=ut.gender and
    agg_child_health.age_tranche=ut.age_tranche and
    agg_child_health.caste=ut.caste and
    agg_child_health.disabled=ut.disabled and
    agg_child_health.minority=ut.minority and
    agg_child_health.resident=ut.resident and
    agg_child_health.aggregation_level = 5
  );
