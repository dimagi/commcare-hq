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
      'sum(wasting_severe_v2), ' ||
      'sum(zscore_grading_hfa_recorded_in_month), ' ||
      'sum(zscore_grading_wfh_recorded_in_month) ';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename4) || ' ' ||
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
    'days_ration_given_child, ' ||
    'zscore_grading_hfa_normal, ' ||
    'zscore_grading_hfa_moderate, ' ||
    'zscore_grading_hfa_severe, ' ||
    'wasting_normal_v2, ' ||
    'wasting_moderate_v2, ' ||
    'wasting_severe_v2, ' ||
    'zscore_grading_hfa_recorded_in_month, ' ||
    'zscore_grading_wfh_recorded_in_month ' ||
    ')' ||
    '(SELECT ' ||
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

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename3) || ' ' ||
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
    'days_ration_given_child, ' ||
    'zscore_grading_hfa_normal, ' ||
    'zscore_grading_hfa_moderate, ' ||
    'zscore_grading_hfa_severe, ' ||
    'wasting_normal_v2, ' ||
    'wasting_moderate_v2, ' ||
    'wasting_severe_v2, ' ||
    'zscore_grading_hfa_recorded_in_month, ' ||
    'zscore_grading_wfh_recorded_in_month ' ||
    ')' ||
    '(SELECT ' ||
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

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename2) || ' ' ||
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
    'days_ration_given_child, ' ||
    'zscore_grading_hfa_normal, ' ||
    'zscore_grading_hfa_moderate, ' ||
    'zscore_grading_hfa_severe, ' ||
    'wasting_normal_v2, ' ||
    'wasting_moderate_v2, ' ||
    'wasting_severe_v2, ' ||
    'zscore_grading_hfa_recorded_in_month, ' ||
    'zscore_grading_wfh_recorded_in_month ' ||
    ')' ||
    '(SELECT ' ||
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

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename1) || ' ' ||
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
    'days_ration_given_child, ' ||
    'zscore_grading_hfa_normal, ' ||
    'zscore_grading_hfa_moderate, ' ||
    'zscore_grading_hfa_severe, ' ||
    'wasting_normal_v2, ' ||
    'wasting_moderate_v2, ' ||
    'wasting_severe_v2, ' ||
    'zscore_grading_hfa_recorded_in_month, ' ||
    'zscore_grading_wfh_recorded_in_month ' ||
    ')' ||
    '(SELECT ' ||
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
