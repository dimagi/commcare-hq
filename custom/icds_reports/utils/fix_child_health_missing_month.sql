UPDATE child_health_monthly child_health
 SET
 	current_month_stunting = CASE
 			WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
 			WHEN NOT (gm.zscore_grading_hfa_last_recorded BETWEEN '2018-05-01' AND '2018-05-31') THEN 'unmeasured'
 			WHEN gm.zscore_grading_hfa = 1 THEN 'severe'
 			WHEN gm.zscore_grading_hfa = 2 THEN 'moderate'
 			WHEN gm.zscore_grading_hfa = 3 THEN 'normal'
 		END,
 	stunting_last_recorded = CASE
			WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
			WHEN gm.zscore_grading_hfa = 1 THEN 'severe'
			WHEN gm.zscore_grading_hfa = 2 THEN 'moderate'
			WHEN gm.zscore_grading_hfa = 3 THEN 'normal'
			ELSE 'unknown'
	END,
	wasting_last_recorded = CASE
			WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
			WHEN gm.zscore_grading_wfh = 1 THEN 'severe'
			WHEN gm.zscore_grading_wfh = 2 THEN 'moderate'
			WHEN gm.zscore_grading_wfh = 3 THEN 'normal'
			ELSE 'unknown'
	END,
	current_month_wasting = CASE
			WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
			WHEN gm.zscore_grading_wfh_last_recorded>='2018-05-01' AND gm.zscore_grading_wfh_last_recorded<'2018-06-01' THEN 'unmeasured'
			WHEN gm.zscore_grading_wfh = 1 THEN 'severe'
			WHEN gm.zscore_grading_wfh = 2 THEN 'moderate'
			WHEN gm.zscore_grading_wfh = 3 THEN 'normal'
			ELSE 'unmeasured'
	END,
	zscore_grading_wfh_recorded_in_month = CASE
			WHEN gm.zscore_grading_wfh_last_recorded>='2018-05-01' AND gm.zscore_grading_wfh_last_recorded<'2018-06-01' THEN 1
			ELSE 0
	END
	FROM icds_dashboard_growth_monitoring_forms gm
	WHERE child_health.month=gm.month
		AND child_health.case_id=gm.case_id
		AND child_health.month='2018-05-01'
		AND gm.month='2018-05-01'
		AND child_health.supervisor_id=gm.supervisor_id;



-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Update on child_health_monthly_323196 child_health  (cost=1.11..5.12 rows=1 width=661)
--                Update on child_health_monthly_default_102648 child_health_1
--                ->  Nested Loop  (cost=1.11..5.12 rows=1 width=661)
--                      ->  Index Scan using icds_dashboard_growth_mo_month_state_id_9dfbeda1_idx_102264 on icds_dashboard_growth_monitoring_forms_102264 gm  (cost=0.56..2.25 rows=1 width=100)
--                            Index Cond: (month = '2018-05-01'::date)
--                      ->  Index Scan using child_health_monthly_default_102648_pkey on child_health_monthly_default_102648 child_health_1  (cost=0.56..2.78 rows=1 width=525)
--                            Index Cond: ((supervisor_id = gm.supervisor_id) AND (case_id = (gm.case_id)::text) AND (month = '2018-05-01'::date))

DROP TABLE IF EXISTS temp_agg_child_my;
CREATE TABLE temp_agg_child_my AS
SELECT
	awc_id,
	chm.month,
	sex,
	age_tranche,
	caste,
	SUM(CASE WHEN chm.current_month_wasting = 'moderate' THEN 1 ELSE 0 END) as wasting_moderate,
	SUM(CASE WHEN chm.current_month_wasting = 'severe' THEN 1 ELSE 0 END) as wasting_severe,
	SUM(CASE WHEN chm.current_month_stunting = 'moderate' THEN 1 ELSE 0 END) as stunting_moderate,
	SUM(CASE WHEN chm.current_month_stunting = 'severe' THEN 1 ELSE 0 END) as stunting_severe,
	SUM(CASE WHEN chm.current_month_wasting = 'normal' THEN 1 ELSE 0 END) as wasting_normal,
	SUM(CASE WHEN chm.current_month_stunting = 'normal' THEN 1 ELSE 0 END) as stunting_normal,
	SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 3 THEN 1 ELSE 0 END) as wasting_normal_v2,
	SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 2 THEN 1 ELSE 0 END) as wasting_moderate_v2,
	SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 1 THEN 1 ELSE 0 END) as wasting_severe_v2,
	COALESCE(chm.disabled, 'no') as coalesce_disabled,
	COALESCE(chm.minority, 'no') as coalesce_minority,
	COALESCE(chm.resident, 'no') as coalesce_resident

	FROM
	"child_health_monthly" chm
	WHERE chm.month='2018-05-01'
	GROUP BY chm.awc_id,
					 chm.month, chm.sex, chm.age_tranche, chm.caste,
					 coalesce_disabled, coalesce_minority, coalesce_resident
	ORDER BY chm.awc_id;



UPDATE "agg_child_health_2018-05-01_5" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2
    from (
        SELECT * from temp_agg_Child_my
    ) ut 
    where (
        agg_child_health.awc_id=ut.awc_id and 
        agg_child_health.month=ut.month and
        agg_child_health.gender=ut.sex and
        agg_child_health.age_tranche=ut.age_tranche and
        agg_child_health.caste=ut.caste and
        agg_child_health.disabled=ut.coalesce_disabled and
        agg_child_health.minority = ut.coalesce_minority and
        agg_child_health.resident = ut.coalesce_resident
            );

Roll ups:

UPDATE "agg_child_health_2018-05-01_4" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2
    from (
        SELECT
        supervisor_id,
        gender,
        age_tranche,
        SUM(wasting_moderate) as wasting_moderate,
        SUM(wasting_severe) as wasting_severe,
        SUM(stunting_moderate) as stunting_moderate,
        SUM(stunting_severe) as stunting_severe,
        SUM(wasting_normal) as wasting_normal,
        SUM(stunting_normal) as stunting_normal,
        SUM(wasting_normal_v2) as wasting_normal_v2,
        SUM(wasting_moderate_v2) as wasting_moderate_v2,
        SUM(wasting_severe_v2) as wasting_severe_v2

        FROM "agg_child_health_2018-05-01_5" agg_child INNER JOIN (SELECT DISTINCT ucr.doc_id FROM "ucr_icds-cas_static-awc_location_88b3f9c3" ucr WHERE ucr.awc_is_test=0) tt ON tt.doc_id = agg_child.awc_id
        GROUP BY state_id, district_id,block_id,supervisor_id, gender, age_tranche
    ) ut 
    WHERE agg_child_health.supervisor_id = ut.supervisor_id and 
      agg_child_health.gender = ut.gender AND
      agg_child_health.age_tranche = ut.age_tranche;


UPDATE "agg_child_health_2018-05-01_3" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2
    from (
        SELECT
        block_id,
        gender,
        age_tranche,
        SUM(wasting_moderate) as wasting_moderate,
        SUM(wasting_severe) as wasting_severe,
        SUM(stunting_moderate) as stunting_moderate,
        SUM(stunting_severe) as stunting_severe,
        SUM(wasting_normal) as wasting_normal,
        SUM(stunting_normal) as stunting_normal,
        SUM(wasting_normal_v2) as wasting_normal_v2,
        SUM(wasting_moderate_v2) as wasting_moderate_v2,
        SUM(wasting_severe_v2) as wasting_severe_v2

        FROM "agg_child_health_2018-05-01_4" agg_child INNER JOIN (SELECT DISTINCT ucr.supervisor_id FROM "ucr_icds-cas_static-awc_location_88b3f9c3" ucr WHERE ucr.supervisor_is_test=0) tt ON tt.supervisor_id = agg_child.supervisor_id
        GROUP BY state_id, district_id,block_id, gender, age_tranche
    ) ut 
    WHERE agg_child_health.block_id = ut.block_id and 
      agg_child_health.gender = ut.gender AND
      agg_child_health.age_tranche = ut.age_tranche;



UPDATE "agg_child_health_2018-05-01_2" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2
    from (
        SELECT
        district_id,
        gender,
        age_tranche,
        SUM(wasting_moderate) as wasting_moderate,
        SUM(wasting_severe) as wasting_severe,
        SUM(stunting_moderate) as stunting_moderate,
        SUM(stunting_severe) as stunting_severe,
        SUM(wasting_normal) as wasting_normal,
        SUM(stunting_normal) as stunting_normal,
        SUM(wasting_normal_v2) as wasting_normal_v2,
        SUM(wasting_moderate_v2) as wasting_moderate_v2,
        SUM(wasting_severe_v2) as wasting_severe_v2

        FROM "agg_child_health_2018-05-01_3" agg_child INNER JOIN (SELECT DISTINCT ucr.block_id FROM "ucr_icds-cas_static-awc_location_88b3f9c3" ucr WHERE ucr.block_is_test=0) tt ON tt.block_id = agg_child.block_id
        GROUP BY state_id, district_id,gender, age_tranche
    ) ut 
    WHERE agg_child_health.district_id = ut.district_id and 
      agg_child_health.gender = ut.gender AND
      agg_child_health.age_tranche = ut.age_tranche;


UPDATE "agg_child_health_2018-05-01_1" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2
    from (
        SELECT
        state_id,
        gender,
        age_tranche,
        SUM(wasting_moderate) as wasting_moderate,
        SUM(wasting_severe) as wasting_severe,
        SUM(stunting_moderate) as stunting_moderate,
        SUM(stunting_severe) as stunting_severe,
        SUM(wasting_normal) as wasting_normal,
        SUM(stunting_normal) as stunting_normal,
        SUM(wasting_normal_v2) as wasting_normal_v2,
        SUM(wasting_moderate_v2) as wasting_moderate_v2,
        SUM(wasting_severe_v2) as wasting_severe_v2

        FROM "agg_child_health_2018-05-01_2" agg_child INNER JOIN (SELECT DISTINCT ucr.district_id FROM "ucr_icds-cas_static-awc_location_88b3f9c3" ucr WHERE ucr.block_is_test=0) tt ON tt.district_id = agg_child.district_id
        GROUP BY state_id, district_id,gender, age_tranche
    ) ut 
    WHERE agg_child_health.state_id = ut.state_id and 
      agg_child_health.gender = ut.gender AND
      agg_child_health.age_tranche = ut.age_tranche;



