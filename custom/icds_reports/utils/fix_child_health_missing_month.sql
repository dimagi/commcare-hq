UPDATE child_health_monthly_2018_05_01
 SET
 	current_month_stunting = tmp.current_month_stunting,
 	stunting_last_recorded = tmp.stunting_last_recorded,
 	wasting_last_recorded = tmp.wasting_last_recorded,
 	current_month_wasting = tmp.current_month_wasting,
 	zscore_grading_wfh_recorded_in_month = tmp.zscore_grading_wfh_recorded_in_month
FROM (
		SELECT
			child_health.case_id as case_id,
			child_health.valid_in_month as valid_in_month,
			child_health.age_tranche as age_tranche,
			CASE
				WHEN NOT (valid_in_month AND age_tranche::Integer <= 60) THEN NULL
				WHEN date_trunc('MONTH', gm.zscore_grading_hfa_last_recorded) != %(start_date)s THEN 'unmeasured'
				WHEN gm.zscore_grading_hfa = 1 THEN 'severe'
				WHEN gm.zscore_grading_hfa = 2 THEN 'moderate'
				WHEN gm.zscore_grading_hfa = 3 THEN 'normal'
				ELSE 'unmeasured' 
			END as current_month_stunting,
			CASE
				WHEN NOT (valid_in_month AND age_tranche::Integer <= 60) THEN NULL
				WHEN gm.zscore_grading_hfa = 1 THEN 'severe'
				WHEN gm.zscore_grading_hfa = 2 THEN 'moderate'
				WHEN gm.zscore_grading_hfa = 3 THEN 'normal'
				ELSE 'unknown'
			END as stunting_last_recorded,
			CASE
				WHEN NOT ((valid_in_month AND age_tranche::Integer <= 60) THEN NULL
				WHEN gm.zscore_grading_wfh = 1 THEN 'severe'
				WHEN gm.zscore_grading_wfh = 2 THEN 'moderate'
				WHEN gm.zscore_grading_wfh = 3 THEN 'normal'
				ELSE 'unknown'
			END as wasting_last_recorded,
			CASE
				WHEN NOT (valid_in_month AND age_tranche::Integer <= 60) THEN NULL
				WHEN date_trunc('MONTH', gm.zscore_grading_wfh_last_recorded) != %(start_date)s THEN 'unmeasured'
				WHEN gm.zscore_grading_wfh = 1 THEN 'severe'
				WHEN gm.zscore_grading_wfh = 2 THEN 'moderate'
				WHEN gm.zscore_grading_wfh = 3 THEN 'normal'
				ELSE 'unmeasured'
			END as current_month_wasting,
			CASE
				WHEN (date_trunc('MONTH', gm.zscore_grading_wfh_last_recorded) = %(start_date)s) THEN 1
				ELSE 0
			END as zscore_grading_wfh_recorded_in_month
				FROM tmp_child_health_monthly_2018_05_01 child_health
				LEFT OUTER JOIN "icds_dashboard_growth_monitoring_forms_2018_05_01" gm ON child_health.doc_id = gm.case_id
              AND gm.month = %(start_date)s
              AND child_health.state_id = gm.state_id
              AND child_health.supervisor_id = gm.supervisor_id
		    ORDER BY child_health.supervisor_id, child_health.awc_id
) as tmp
WHERE case_id = tmp.case_id;

-- Second query to update agg_child_table

UPDATE agg_child_health
 SET wasting_moderate = tmp.wasting_moderate,
 		 wasting_severe = tmp.wasting_severe,
 		 wasting_normal = tmp.wasting_normal,
 		 wasting_normal_v2 = tmp.wasting_normal_v2,
 		 wasting_moderate_v2 = tmp.wasting_moderate_v2,
 		 wasting_severe_v2 = tmp.wasting_severe_v2,
 		 stunting_moderate = tmp.stunting_moderate,
 		 stunting_severe = tmp.stunting_severe,
 		 stunting_normal = tmp.stunting_normal
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
 			SUM(CASE WHEN chm.current_month_stunting = 'moderate' THEN 1 ELSE 0 END) as stunting_moderate,
 			SUM(CASE WHEN chm.current_month_stunting = 'severe' THEN 1 ELSE 0 END) as stunting_severe,
 			SUM(CASE WHEN chm.current_month_wasting = 'normal' THEN 1 ELSE 0 END) as wasting_normal,
 			SUM(CASE WHEN chm.current_month_stunting = 'normal' THEN 1 ELSE 0 END) as stunting_normal,
 			SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 3 THEN 1 ELSE 0 END) as wasting_normal_v2,
 			SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 2 THEN 1 ELSE 0 END) as wasting_moderate_v2,
 			SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 1 THEN 1 ELSE 0 END) as wasting_severe_v2
 		FROM "child_health_monthly_2019-01-01" chm
      LEFT OUTER JOIN "awc_location" awc_loc ON (
        awc_loc.supervisor_id = chm.supervisor_id AND awc_loc.doc_id = chm.awc_id
      )
      WHERE chm.month = %(start_date)s
            AND awc_loc.state_id != ''
            AND awc_loc.state_id IS NOT NULL
            AND chm.supervisor_id >= '0'
            AND chm.supervisor_id < '1'
      GROUP BY awc_loc.state_id, awc_loc.district_id, awc_loc.block_id, chm.supervisor_id, chm.awc_id,
               chm.month, chm.sex, chm.age_tranche, chm.caste,
               coalesce_disabled, coalesce_minority, coalesce_resident; 
 	) tmp
 	WHERE state_id = tmp.state_id
 		AND district_id = tmp.district_id
 		AND block_id = tmp.block_id
 		AND supervisor_id = tmp.supervisor_id
 		AND awc_id = tmp.awc_id
 		AND month = tmp.month




