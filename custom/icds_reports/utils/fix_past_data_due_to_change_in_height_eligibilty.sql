-- child health table fix
UPDATE child_health_monthly
   SET
      height_measured_in_month = tmp.height_measured_in_month, 
      current_month_stunting = tmp.current_month_stunting,
      stunting_last_recorded = tmp.stunting_last_recorded,
      wasting_last_recorded = tmp.wasting_last_recorded,
      current_month_wasting = tmp.current_month_wasting
   FROM (
      SELECT
         chm.case_id as case_id,
         chm.valid_in_month as valid_in_month,
         chm.age_tranche as age_tranche,
         CASE
            WHEN NOT (chm.valid_in_month::boolean AND chm.age_tranche::Integer <= 60) THEN NULL
         ELSE
            chm.current_month_stunting
         END as current_month_stunting,
         CASE
            WHEN NOT (chm.valid_in_month::boolean AND chm.age_tranche::Integer <= 60) THEN NULL
         ELSE
            chm.stunting_last_recorded
         END as stunting_last_recorded,
         CASE
            WHEN NOT (chm.valid_in_month::boolean AND chm.age_tranche::Integer <= 60) THEN NULL
         ELSE
            chm.wasting_last_recorded
         END as wasting_last_recorded,
         CASE
            WHEN NOT (chm.valid_in_month::boolean AND chm.age_tranche::Integer <= 60) THEN NULL
         ELSE
            chm.current_month_wasting
         END as current_month_wasting,
         CASE
            WHEN date_trunc('MONTH', gm.height_child_last_recorded) = '2018-06-01' AND (chm.valid_in_month::boolean AND chm.age_tranche::Integer <= 60) THEN 1
         ELSE
            0
         END as height_measured_in_month
         FROM child_health_monthly chm
         LEFT OUTER JOIN icds_dashboard_growth_monitoring_forms gm ON chm.case_id = gm.case_id
                     AND gm.month = '2018-06-01'
              AND chm.state_id = gm.state_id
              AND chm.supervisor_id = gm.supervisor_id
         ORDER BY chm.supervisor_id, chm.awc_id
) as tmp
WHERE case_id = tmp.case_id

-- aggegrate child health table fix
UPDATE agg_child_health
 SET weighed_and_height_measured_in_month = tmp.weighed_and_height_measured_in_month,
       height_measured_in_month = tmp.height_measured_in_month,
       stunting_normal = tmp.stunting_normal,
       stunting_severe = tmp.stunting_severe,
       stunting_moderate = tmp.stunting_moderate,
       wasting_moderate = tmp.wasting_moderate,
       wasting_severe = tmp.wasting_severe,
       wasting_normal = tmp.wasting_normal
   FROM (
      SELECT
         awc_loc.state_id as state_id,
         awc_loc.district_id as district_id,
         awc_loc.block_id as block_id,
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

      FROM "child_health_monthly" chm
      LEFT OUTER JOIN "awc_location" awc_loc ON (
        awc_loc.supervisor_id = chm.supervisor_id AND awc_loc.doc_id = chm.awc_id
      )
      WHERE chm.month = '2018-06-01'
            AND awc_loc.state_id != ''
            AND awc_loc.state_id IS NOT NULL
            AND chm.supervisor_id >= '0'
            AND chm.supervisor_id < '1'
      GROUP BY awc_loc.state_id, awc_loc.district_id, awc_loc.block_id, chm.supervisor_id, chm.awc_id,
               chm.month, chm.sex, chm.age_tranche, chm.caste
   ) as tmp
   WHERE state_id = tmp.state_id
      AND district_id = tmp.district_id
      AND block_id = tmp.block_id
      AND supervisor_id = tmp.supervisor_id
      AND awc_id = tmp.awc_id
      AND month = tmp.month

