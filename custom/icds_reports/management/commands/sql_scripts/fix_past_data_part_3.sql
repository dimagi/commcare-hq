UPDATE "agg_child_health_{start_date}_5" agg_child_health
  SET
    wasting_moderate = ut.wasting_moderate,
    wasting_severe = ut.wasting_severe,
    wasting_normal = ut.wasting_normal,
    stunting_moderate = ut.stunting_moderate,
    stunting_severe = ut.stunting_severe,
    stunting_normal = ut.stunting_normal,
    height_measured_in_month = ut.height_measured_in_month,
    weighed_and_height_measured_in_month = ut.weighed_and_height_measured_in_month
  FROM temp_chm_local ut
  WHERE (
    agg_child_health.awc_id=ut.awc_id and 
    agg_child_health.month=ut.month and
    agg_child_health.gender=ut.sex and
    agg_child_health.age_tranche=ut.age_tranche and
    agg_child_health.caste=ut.caste and
    agg_child_health.disabled=ut.coalesce_disabled and
    agg_child_health.minority = ut.coalesce_minority and
    agg_child_health.resident = ut.coalesce_resident
  );
