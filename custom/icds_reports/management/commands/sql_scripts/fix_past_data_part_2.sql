DROP TABLE IF EXISTS temp_chm;
CREATE UNLOGGED TABLE temp_chm As select awc_id, supervisor_id, month, gender, age_tranche, caste, height_eligible, wasting_moderate, wasting_severe, wasting_normal, stunting_moderate, stunting_severe, stunting_normal, height_measured_in_month, weighed_and_height_measured_in_month, disabled, minority, resident from agg_child_health where 1=0;
SELECT create_distributed_table('temp_chm', 'supervisor_id');
INSERT INTO "temp_chm" (
  awc_id, supervisor_id, month, gender, age_tranche, caste, height_eligible,
  wasting_moderate, wasting_severe, wasting_normal, stunting_moderate, stunting_severe,
  stunting_normal, height_measured_in_month, weighed_and_height_measured_in_month, disabled,
  minority, resident
) (
  SELECT
      chm.awc_id, chm.supervisor_id, chm.month, chm.sex, chm.age_tranche, chm.caste,
      SUM(CASE WHEN chm.age_tranche NOT IN ('72') AND chm.valid_in_month = 1 THEN 1 ELSE 0 END) as height_eligible,
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
