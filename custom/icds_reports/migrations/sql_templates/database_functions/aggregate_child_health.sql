-- Aggregate into agg_child_health
CREATE OR REPLACE FUNCTION aggregate_child_health(date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename1 text;
  _tablename2 text;
  _tablename3 text;
  _tablename4 text;
  _tablename5 text;
  _ucr_child_monthly_table text;
  _child_health_monthly_table text;
  _start_date date;
  _end_date date;
  _all_text text;
  _null_value text;
  _blank_value text;
  _no_text text;
  _rollup_text text;
  _rollup_text2 text;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _tablename1 := 'agg_child_health' || '_' || _start_date || '_1';
  _tablename2 := 'agg_child_health' || '_' || _start_date || '_2';
  _tablename3 := 'agg_child_health' || '_' || _start_date || '_3';
  _tablename4 := 'agg_child_health' || '_' || _start_date || '_4';
  _tablename5 := 'agg_child_health' || '_' || _start_date || '_5';
  _child_health_monthly_table := 'child_health_monthly' || '_' || _start_date;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('child_health_monthly') INTO _ucr_child_monthly_table;
  _all_text = 'All';
  _null_value = NULL;
  _blank_value = '';
  _no_text = 'no';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename5) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'gender, ' ||
    'age_tranche, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'valid_in_month, ' ||
    'nutrition_status_weighed, ' ||
    'nutrition_status_unweighed, ' ||
    'nutrition_status_normal, ' ||
    'nutrition_status_moderately_underweight, ' ||
    'nutrition_status_severely_underweight, ' ||
    'wer_eligible, ' ||
    'thr_eligible, ' ||
    'rations_21_plus_distributed, ' ||
    'pse_eligible, ' ||
    'pse_attended_16_days, ' ||
    'born_in_month, ' ||
    'low_birth_weight_in_month, ' ||
    'bf_at_birth, ' ||
    'ebf_eligible, ' ||
    'ebf_in_month, ' ||
    'cf_eligible, ' ||
    'cf_in_month, ' ||
    'cf_diet_diversity, ' ||
    'cf_diet_quantity, ' ||
    'cf_demo, ' ||
    'cf_handwashing, ' ||
    'counsel_increase_food_bf, ' ||
    'counsel_manage_breast_problems, ' ||
    'counsel_ebf, ' ||
    'counsel_adequate_bf, ' ||
    'counsel_pediatric_ifa, ' ||
    'counsel_play_cf_video, ' ||
    'fully_immunized_eligible, ' ||
    'fully_immunized_on_time, ' ||
    'fully_immunized_late, ' ||
    'has_aadhar_id, ' ||
    'aggregation_level, ' ||
    'pnc_eligible, ' ||
    'height_eligible, ' ||
    'wasting_moderate, ' ||
    'wasting_severe, ' ||
    'stunting_moderate, ' ||
    'stunting_severe, ' ||
    'cf_initiation_in_month, ' ||
    'cf_initiation_eligible, ' ||
    'height_measured_in_month, ' ||
    'wasting_normal, ' ||
    'stunting_normal, ' ||
    'valid_all_registered_in_month, ' ||
    'ebf_no_info_recorded, ' ||
    'weighed_and_height_measured_in_month,' ||
    'weighed_and_born_in_month, ' ||
    'zscore_grading_hfa_normal, ' ||
    'zscore_grading_hfa_moderate, ' ||
    'zscore_grading_hfa_severe, ' ||
    'wasting_normal_v2, ' ||
    'wasting_moderate_v2, ' ||
    'wasting_severe_v2 ' ||
    ')' ||
  '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'sex, ' ||
    'age_tranche, ' ||
    'caste, ' ||
    'COALESCE(disabled, ' || quote_nullable(_no_text) || ') as coalesce_disabled, ' ||
    'COALESCE(minority, ' || quote_nullable(_no_text) || ') as coalesce_minority, ' ||
    'COALESCE(resident, ' || quote_nullable(_no_text) || ') as coalesce_resident, ' ||
    'sum(valid_in_month), ' ||
    'sum(nutrition_status_weighed), ' ||
    'sum(nutrition_status_unweighed), ' ||
    'sum(CASE WHEN nutrition_status_normal = 1 AND nutrition_status_weighed = 1 THEN 1 ELSE 0 END), ' ||
    'sum(CASE WHEN nutrition_status_moderately_underweight = 1 AND nutrition_status_weighed = 1 THEN 1 ELSE 0 END), ' ||
    'sum(CASE WHEN nutrition_status_severely_underweight = 1 AND nutrition_status_weighed = 1 THEN 1 ELSE 0 END), ' ||
    'sum(wer_eligible), ' ||
    '0, ' ||
    '0, ' ||
    'sum(pse_eligible), ' ||
    'sum(pse_attended_16_days), ' ||
    'sum(born_in_month), ' ||
    'sum(low_birth_weight_born_in_month), ' ||
    'sum(bf_at_birth_born_in_month), ' ||
    'sum(ebf_eligible), ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    'sum(fully_immunized_eligible), ' ||
    'sum(fully_immunized_on_time), ' ||
    'sum(fully_immunized_late), ' ||
    'sum(has_aadhar_id), ' ||
    '5, ' ||
    'sum(pnc_eligible), ' ||
    'sum(height_eligible), ' ||
    'sum(CASE WHEN wasting_moderate = 1 AND nutrition_status_weighed = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
    'sum(CASE WHEN wasting_severe = 1 AND nutrition_status_weighed = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
    'sum(CASE WHEN stunting_moderate = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
    'sum(CASE WHEN stunting_severe = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
    '0, ' ||
    '0, ' ||
    'sum(height_measured_in_month), ' ||
    'sum(CASE WHEN wasting_normal = 1 AND nutrition_status_weighed = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
    'sum(CASE WHEN stunting_normal = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
    'sum(valid_all_registered_in_month), ' ||
    '0, ' ||
    'sum(CASE WHEN nutrition_status_weighed = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
    'sum(CASE WHEN (born_in_month = 1 AND (nutrition_status_weighed = 1 OR low_birth_weight_born_in_month = 1)) THEN 1 ELSE 0 END), ' ||
    '0, 0, 0, 0, 0, 0 ' ||
    'FROM ' || quote_ident(_ucr_child_monthly_table) || ' ' ||
    'WHERE state_id != ' || quote_literal(_blank_value) ||  ' AND month = ' || quote_literal(_start_date) || ' ' ||
    'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, sex, age_tranche, caste, coalesce_disabled, coalesce_minority, coalesce_resident)';

  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx1') || ' ON ' || quote_ident(_tablename5) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx4') || ' ON ' || quote_ident(_tablename5) || '(supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx5') || ' ON ' || quote_ident(_tablename5) || '(awc_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx6') || ' ON ' || quote_ident(_tablename5) || '(gender)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx7') || ' ON ' || quote_ident(_tablename5) || '(age_tranche)';

  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_child_health SET ' ||
    'cf_eligible = temp.cf_eligible, ' ||
    'cf_in_month = temp.cf_in_month, ' ||
    'cf_diet_diversity = temp.cf_diet_diversity, ' ||
    'cf_diet_quantity = temp.cf_diet_quantity, ' ||
    'cf_demo = temp.cf_demo, ' ||
    'cf_handwashing = temp.cf_handwashing, ' ||
    'counsel_pediatric_ifa = temp.counsel_pediatric_ifa, ' ||
    'counsel_play_cf_video = temp.counsel_comp_feeding_vid, ' ||
    'cf_initiation_in_month = temp.cf_initiation_in_month, ' ||
    'cf_initiation_eligible = temp.cf_initiation_eligible, ' ||
    'days_ration_given_child = temp.days_ration_given_child, ' ||
    'zscore_grading_hfa_normal = temp.zscore_grading_hfa_normal, ' ||
    'zscore_grading_hfa_moderate = temp.zscore_grading_hfa_moderate, ' ||
    'zscore_grading_hfa_severe = temp.zscore_grading_hfa_severe, ' ||
    'wasting_normal_v2 = temp.wasting_normal_v2, ' ||
    'wasting_moderate_v2 = temp.wasting_moderate_v2, ' ||
    'wasting_severe_v2 = temp.wasting_severe_v2, ' ||
    'ebf_in_month = temp.ebf_in_month, ' ||
    'counsel_increase_food_bf = temp.counsel_increase_food_bf, ' ||
    'counsel_manage_breast_problems = temp.counsel_manage_breast_problems, ' ||
    'counsel_ebf = temp.counsel_ebf, ' ||
    'counsel_adequate_bf = temp.counsel_adequate_bf, ' ||
    'ebf_no_info_recorded = temp.ebf_no_info_recorded, ' ||
    'thr_eligible = temp.thr_eligible, ' ||
    'rations_21_plus_distributed = temp.rations_21_plus_distributed ' ||
    'FROM (SELECT ' ||
      'awc_id, month, sex, age_tranche, caste, ' ||
      'coalesce(disabled, ' || quote_nullable(_no_text) || ') as coalesce_disabled, ' ||
      'coalesce(minority, ' || quote_nullable(_no_text) || ') as coalesce_minority, ' ||
      'coalesce(resident, ' || quote_nullable(_no_text) || ') as coalesce_resident, ' ||
      'sum(cf_eligible) as cf_eligible, ' ||
      'sum(cf_in_month) as cf_in_month, ' ||
      'sum(cf_diet_diversity) as cf_diet_diversity, ' ||
      'sum(cf_diet_quantity) as cf_diet_quantity, ' ||
      'sum(cf_demo) as cf_demo, ' ||
      'sum(cf_handwashing) as cf_handwashing, ' ||
      'sum(counsel_pediatric_ifa) as counsel_pediatric_ifa, ' ||
      'sum(counsel_comp_feeding_vid) as counsel_comp_feeding_vid, ' ||
      'sum(cf_initiation_in_month) as cf_initiation_in_month, ' ||
      'sum(cf_initiation_eligible) as cf_initiation_eligible, ' ||
      'sum(days_ration_given_child) as days_ration_given_child, ' ||
      'sum(CASE WHEN zscore_grading_hfa_recorded_in_month = 1 AND zscore_grading_hfa = 3 THEN 1 ELSE 0 END) as zscore_grading_hfa_normal, ' ||
      'sum(CASE WHEN zscore_grading_hfa_recorded_in_month = 1 AND zscore_grading_hfa = 2 THEN 1 ELSE 0 END) as zscore_grading_hfa_moderate, ' ||
      'sum(CASE WHEN zscore_grading_hfa_recorded_in_month = 1 AND zscore_grading_hfa = 1 THEN 1 ELSE 0 END) as zscore_grading_hfa_severe, ' ||
      'sum(CASE ' ||
        'WHEN zscore_grading_wfh_recorded_in_month = 1 AND zscore_grading_wfh = 3 THEN 1 ' ||
        'WHEN muac_grading_recorded_in_month = 1 AND muac_grading = 3 THEN 1 ' ||
        'ELSE 0 END) as wasting_normal_v2, ' ||
      'sum(CASE ' ||
        'WHEN zscore_grading_wfh_recorded_in_month = 1 AND zscore_grading_wfh = 2 THEN 1 ' ||
        'WHEN muac_grading_recorded_in_month = 1 AND muac_grading = 2 THEN 1 ' ||
        'ELSE 0 END) as wasting_moderate_v2, ' ||
      'sum(CASE ' ||
        'WHEN zscore_grading_wfh_recorded_in_month = 1 AND zscore_grading_wfh = 1 THEN 1 ' ||
        'WHEN muac_grading_recorded_in_month = 1 AND muac_grading = 1 THEN 1 ' ||
        'ELSE 0 END) as wasting_severe_v2, ' ||
      'sum(ebf_in_month) as ebf_in_month, ' ||
      'sum(counsel_increase_food_bf) as counsel_increase_food_bf, ' ||
      'sum(counsel_manage_breast_problems) as counsel_manage_breast_problems, ' ||
      'sum(counsel_ebf) as counsel_ebf, ' ||
      'sum(counsel_adequate_bf) as counsel_adequate_bf, ' ||
      'sum(ebf_no_info_recorded) as ebf_no_info_recorded, ' ||
      'sum(thr_eligible) as thr_eligible, ' ||
      'sum(CASE WHEN num_rations_distributed >= 21 THEN 1 ELSE 0 END) as rations_21_plus_distributed ' ||
      'FROM ' || quote_ident(_child_health_monthly_table) || ' ' ||
      'GROUP BY awc_id, month, sex, age_tranche, caste, coalesce_disabled, coalesce_minority, coalesce_resident) temp ' ||
    'WHERE temp.awc_id = agg_child_health.awc_id AND temp.month = agg_child_health.month AND temp.sex = agg_child_health.gender ' ||
      'AND temp.age_tranche = agg_child_health.age_tranche AND temp.caste = agg_child_health.caste ' ||
      'AND temp.coalesce_disabled = agg_child_health.disabled AND temp.coalesce_minority = agg_child_health.minority ' ||
      'AND temp.coalesce_resident = agg_child_health.resident';

  --Roll up by location
  _rollup_text = 'sum(valid_in_month), ' ||
    'sum(nutrition_status_weighed), ' ||
    'sum(nutrition_status_unweighed), ' ||
    'sum(nutrition_status_normal), ' ||
    'sum(nutrition_status_moderately_underweight), ' ||
    'sum(nutrition_status_severely_underweight), ' ||
    'sum(wer_eligible), ' ||
    'sum(thr_eligible), ' ||
    'sum(rations_21_plus_distributed), ' ||
    'sum(pse_eligible), ' ||
    'sum(pse_attended_16_days), ' ||
    'sum(born_in_month), ' ||
    'sum(low_birth_weight_in_month), ' ||
    'sum(bf_at_birth), ' ||
    'sum(ebf_eligible), ' ||
    'sum(ebf_in_month), ' ||
    'sum(cf_eligible), ' ||
    'sum(cf_in_month), ' ||
    'sum(cf_diet_diversity), ' ||
    'sum(cf_diet_quantity), ' ||
    'sum(cf_demo), ' ||
    'sum(cf_handwashing), ' ||
    'sum(counsel_increase_food_bf), ' ||
    'sum(counsel_manage_breast_problems), ' ||
    'sum(counsel_ebf), ' ||
    'sum(counsel_adequate_bf), ' ||
    'sum(counsel_pediatric_ifa), ' ||
    'sum(counsel_play_cf_video), ' ||
    'sum(fully_immunized_eligible), ' ||
    'sum(fully_immunized_on_time), ' ||
    'sum(fully_immunized_late), ' ||
    'sum(has_aadhar_id), ';

  _rollup_text2 = 'sum(pnc_eligible), ' ||
    'sum(height_eligible), ' ||
      'sum(wasting_moderate), ' ||
      'sum(wasting_severe), ' ||
      'sum(stunting_moderate), ' ||
      'sum(stunting_severe), ' ||
      'sum(cf_initiation_in_month), ' ||
      'sum(cf_initiation_eligible), ' ||
      'sum(height_measured_in_month), ' ||
      'sum(wasting_normal), ' ||
      'sum(stunting_normal), ' ||
      'sum(valid_all_registered_in_month), ' ||
      'sum(ebf_no_info_recorded), ' ||
      'sum(weighed_and_height_measured_in_month), ' ||
      'sum(weighed_and_born_in_month), ' ||
      'sum(days_ration_given_child), ' ||
      'sum(zscore_grading_hfa_normal), ' ||
      'sum(zscore_grading_hfa_moderate), ' ||
      'sum(zscore_grading_hfa_severe), ' ||
      'sum(wasting_normal_v2), ' ||
      'sum(wasting_moderate_v2), ' ||
      'sum(wasting_severe_v2) ';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename4) || '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    'gender, ' ||
    'age_tranche, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    _rollup_text ||
    '4, ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename5) || ' ' ||
    'GROUP BY state_id, district_id, block_id, supervisor_id, month, gender, age_tranche)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx1') || ' ON ' || quote_ident(_tablename4) || '(state_id, district_id, block_id, supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx4') || ' ON ' || quote_ident(_tablename5) || '(supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx5') || ' ON ' || quote_ident(_tablename4) || '(gender)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx6') || ' ON ' || quote_ident(_tablename4) || '(age_tranche)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename3) || '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    'gender, ' ||
    'age_tranche, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    _rollup_text ||
    '3, ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename4) || ' ' ||
    'GROUP BY state_id, district_id, block_id, month, gender, age_tranche)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx1') || ' ON ' || quote_ident(_tablename3) || '(state_id, district_id, block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx4') || ' ON ' || quote_ident(_tablename3) || '(gender)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx5') || ' ON ' || quote_ident(_tablename3) || '(age_tranche)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename2) || '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    'gender, ' ||
    'age_tranche, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    _rollup_text ||
    '2, ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename3) || ' ' ||
    'GROUP BY state_id, district_id, month, gender, age_tranche)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx1') || ' ON ' || quote_ident(_tablename2) || '(state_id, district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx3') || ' ON ' || quote_ident(_tablename2) || '(gender)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx4') || ' ON ' || quote_ident(_tablename2) || '(age_tranche)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename1) || '(SELECT ' ||
    'state_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    'gender, ' ||
    'age_tranche, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    _rollup_text ||
    '1, ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename2) || ' ' ||
    'GROUP BY state_id, month, gender, age_tranche)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx1') || ' ON ' || quote_ident(_tablename1) || '(state_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx2') || ' ON ' || quote_ident(_tablename1) || '(gender)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx3') || ' ON ' || quote_ident(_tablename1) || '(age_tranche)';
END;
$BODY$
LANGUAGE plpgsql;
