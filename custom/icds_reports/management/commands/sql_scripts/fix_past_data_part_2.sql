DROP TABLE IF EXISTS temp_chm;
CREATE UNLOGGED TABLE temp_chm As select awc_id, supervisor_id, month, gender, age_tranche, caste, lunch_count_21_days, disabled, minority, resident from agg_child_health where 1=0;
SELECT create_distributed_table('temp_chm', 'supervisor_id');
INSERT INTO "temp_chm" (
  awc_id, supervisor_id, month, gender, age_tranche, caste, lunch_count_21_days, disabled,
  minority, resident
) (
  SELECT
      chm.awc_id, chm.supervisor_id, chm.month, chm.sex, chm.age_tranche, chm.caste,
      COUNT(*) FILTER (WHERE chm.lunch_count >= 21) as lunch_count_21_days,
      COALESCE(chm.disabled, 'no') as coalesce_disabled,
      COALESCE(chm.minority, 'no') as coalesce_minority,
      COALESCE(chm.resident, 'no') as coalesce_resident
    FROM
      "child_health_monthly" chm
    WHERE
      chm.month = '{start_date}'
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
);
DROP TABLE IF EXISTS temp_chm_local;
CREATE TABLE temp_chm_local AS SELECT * from temp_chm
