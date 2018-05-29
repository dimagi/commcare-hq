CREATE OR REPLACE FUNCTION create_child_health_monthly_view() RETURNS VOID AS
$BODY$
DECLARE
  _ucr_child_list_table text;
BEGIN
  EXECUTE format('SELECT table_name FROM ucr_table_name_mapping WHERE table_type = %s', '''child_list''') INTO _ucr_child_list_table;

  EXECUTE 'DROP VIEW IF EXISTS child_health_monthly_view CASCADE';
  EXECUTE format('CREATE VIEW child_health_monthly_view AS ' ||
    'SELECT' ||
        '"child_list".case_id, ' ||
        '"child_list".awc_id, ' ||
        '"child_list".supervisor_id, ' ||
        '"child_list".block_id, ' ||
        '"child_list".district_id, ' ||
        '"child_list".state_id, ' ||
        '"child_list".name AS person_name, ' ||
        '"child_list".mother_name, ' ||
        '"child_list".dob, ' ||
        '"child_list".sex, ' ||
        'child_health_monthly.month, ' ||
        'child_health_monthly.age_in_months, ' ||
        'child_health_monthly.open_in_month, ' ||
        'child_health_monthly.valid_in_month, ' ||
        'child_health_monthly.nutrition_status_last_recorded, ' ||
        'child_health_monthly.current_month_nutrition_status, ' ||
        'child_health_monthly.pse_days_attended, ' ||
        'child_health_monthly.recorded_weight, ' ||
        'child_health_monthly.recorded_height, ' ||
        'child_health_monthly.current_month_stunting, ' ||
        'child_health_monthly.current_month_wasting, ' ||
        'child_health_monthly.thr_eligible, ' ||
        'GREATEST(child_health_monthly.fully_immunized_on_time, child_health_monthly.fully_immunized_late) AS fully_immunized, ' ||
        'CASE WHEN child_health_monthly.current_month_nutrition_status = %2$s THEN 1' ||
            'WHEN child_health_monthly.current_month_nutrition_status = %3$s THEN 2' ||
            'WHEN child_health_monthly.current_month_nutrition_status = %6$s THEN 3' ||
            'ELSE 4 END AS current_month_nutrition_status_sort,' ||
        'CASE WHEN child_health_monthly.current_month_stunting = %4$s THEN 1' ||
            'WHEN child_health_monthly.current_month_stunting = %5$s THEN 2' ||
            'WHEN child_health_monthly.current_month_stunting = %6$s THEN 3' ||
            'ELSE 4 END AS current_month_stunting_sort,' ||
        'CASE WHEN child_health_monthly.current_month_wasting = %4$s THEN 1' ||
            'WHEN child_health_monthly.current_month_wasting = %5$s THEN 2' ||
            'WHEN child_health_monthly.current_month_wasting = %6$s THEN 3' ||
            'ELSE 4 END AS current_month_wasting_sort,' ||
        'CASE ' ||
          'WHEN child_health_monthly.zscore_grading_hfa = 1 AND child_health_monthly.zscore_grading_hfa_recorded_in_month = 1 THEN %4$s ' ||
          'WHEN child_health_monthly.zscore_grading_hfa = 2 AND child_health_monthly.zscore_grading_hfa_recorded_in_month = 1 THEN %5$s ' ||
          'WHEN child_health_monthly.zscore_grading_hfa = 3 AND child_health_monthly.zscore_grading_hfa_recorded_in_month = 1 THEN %6$s ' ||
          'ELSE %7$s END AS current_month_stunting_v2, ' ||
        'CASE ' ||
          'WHEN (child_health_monthly.zscore_grading_wfh = 1 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 1 AND child_health_monthly.muac_grading_recorded_in_month = 1) THEN %4$s ' ||
          'WHEN (child_health_monthly.zscore_grading_wfh = 2 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 2 AND child_health_monthly.muac_grading_recorded_in_month = 2) THEN %5$s ' ||
          'WHEN (child_health_monthly.zscore_grading_wfh = 3 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 3 AND child_health_monthly.muac_grading_recorded_in_month = 3) THEN %6$s ' ||
          'ELSE %7$s END AS current_month_wasting_v2, ' ||
        'CASE ' ||
          'WHEN child_health_monthly.zscore_grading_hfa_recorded_in_month = 1 THEN child_health_monthly.zscore_grading_hfa ' ||
          'ELSE 4 END AS current_month_stunting_v2_sort,' ||
        'CASE ' ||
          'WHEN (child_health_monthly.zscore_grading_wfh = 1 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 1 AND child_health_monthly.muac_grading_recorded_in_month = 1) THEN 1 ' ||
          'WHEN (child_health_monthly.zscore_grading_wfh = 2 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 2 AND child_health_monthly.muac_grading_recorded_in_month = 2) THEN 2 ' ||
          'WHEN (child_health_monthly.zscore_grading_wfh = 3 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 3 AND child_health_monthly.muac_grading_recorded_in_month = 3) THEN 3 ' ||
          'ELSE 4 END AS current_month_wasting_v2_sort ' ||
   'FROM %1$I "child_list"' ||
     'LEFT JOIN child_health_monthly child_health_monthly ON "child_list".doc_id = child_health_monthly.case_id',
     _ucr_child_list_table, '''severely_underweight''', '''moderately_underweight''', '''severe''', '''moderate''', '''normal''', '''''');
END;
$BODY$
LANGUAGE plpgsql;