
CREATE OR REPLACE FUNCTION aggregate_ccs_record(date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename1 text;
  _tablename2 text;
  _tablename3 text;
  _tablename4 text;
  _tablename5 text;
  _ucr_ccs_record_table text;
  _ccs_record_monthly_table text;
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
  _tablename1 := 'agg_ccs_record' || '_' || _start_date || '_1';
  _tablename2 := 'agg_ccs_record' || '_' || _start_date || '_2';
  _tablename3 := 'agg_ccs_record' || '_' || _start_date || '_3';
  _tablename4 := 'agg_ccs_record' || '_' || _start_date || '_4';
  _tablename5 := 'agg_ccs_record' || '_' || _start_date || '_5';
  _ccs_record_monthly_table := 'ccs_record_monthly' || '_' || _start_date;
  _all_text = 'All';
  _null_value = NULL;
  _blank_value = '';
  _no_text = 'no';
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('ccs_record_monthly') INTO _ucr_ccs_record_table;

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename5) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'ccs_status, ' ||
    'trimester, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'valid_in_month, ' ||
    'lactating, ' ||
    'pregnant, ' ||
    'thr_eligible, ' ||
    'rations_21_plus_distributed, ' ||
    'tetanus_complete, ' ||
    'delivered_in_month, ' ||
    'anc1_received_at_delivery, ' ||
    'anc2_received_at_delivery, ' ||
    'anc3_received_at_delivery, ' ||
    'anc4_received_at_delivery, ' ||
    'registration_trimester_at_delivery, ' ||
    'using_ifa, ' ||
    'ifa_consumed_last_seven_days, ' ||
    'anemic_normal, ' ||
    'anemic_moderate, ' ||
    'anemic_severe, ' ||
    'anemic_unknown, ' ||
    'extra_meal, ' ||
    'resting_during_pregnancy, ' ||
    'bp1_complete, ' ||
    'bp2_complete, ' ||
    'bp3_complete, ' ||
    'pnc_complete, ' ||
    'trimester_2, ' ||
    'trimester_3, ' ||
    'postnatal, ' ||
    'counsel_bp_vid, ' ||
    'counsel_preparation, ' ||
    'counsel_immediate_bf, ' ||
    'counsel_fp_vid, ' ||
    'counsel_immediate_conception, ' ||
    'counsel_accessible_postpartum_fp, ' ||
    'has_aadhar_id, ' ||
    'aggregation_level, ' ||
    'valid_all_registered_in_month, ' ||
    'institutional_delivery_in_month, ' ||
    'lactating_all, ' ||
    'pregnant_all ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'ccs_status, ' ||
    'COALESCE(trimester::text, ' || quote_nullable(_blank_value) || '), ' ||
    'caste, ' ||
    'COALESCE(disabled, ' || quote_nullable(_no_text) || '), ' ||
    'COALESCE(minority, ' || quote_nullable(_no_text) || '), ' ||
    'COALESCE(resident, ' || quote_nullable(_no_text) || '), ' ||
    'sum(valid_in_month), ' ||
    'sum(lactating), ' ||
    'sum(pregnant), ' ||
    '0, ' ||
    '0, ' ||
    'sum(tetanus_complete), ' ||
    'sum(delivered_in_month), ' ||
    'sum(anc1_received_at_delivery), ' ||
    'sum(anc2_received_at_delivery), ' ||
    'sum(anc3_received_at_delivery), ' ||
    'sum(anc4_received_at_delivery), ' ||
    'avg(registration_trimester_at_delivery), ' ||
    'sum(using_ifa), ' ||
    'sum(ifa_consumed_last_seven_days), ' ||
    'sum(anemic_normal), ' ||
    'sum(anemic_moderate), ' ||
    'sum(anemic_severe), ' ||
    'sum(anemic_unknown), ' ||
    'sum(extra_meal), ' ||
    'sum(resting_during_pregnancy), ' ||
    'sum(bp1_complete), ' ||
    'sum(bp2_complete), ' ||
    'sum(bp3_complete), ' ||
    'sum(pnc_complete), ' ||
    'sum(trimester_2), ' ||
    'sum(trimester_3), ' ||
    'sum(postnatal), ' ||
    'sum(counsel_bp_vid), ' ||
    'sum(counsel_preparation), ' ||
    'sum(counsel_immediate_bf), ' ||
    'sum(counsel_fp_vid), ' ||
    'sum(counsel_immediate_conception), ' ||
    'sum(counsel_accessible_postpartum_fp), ' ||
    'sum(has_aadhar_id), ' ||
    '5, '
    'sum(valid_all_registered_in_month), ' ||
    'sum(institutional_delivery_in_month), ' ||
    'sum(lactating_all), ' ||
    'sum(pregnant_all) ' ||
    'FROM ' || quote_ident(_ucr_ccs_record_table) || ' ' ||
    'WHERE state_id != ' || quote_literal(_blank_value) ||  ' AND month = ' || quote_literal(_start_date) || ' ' ||
    'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, ccs_status, trimester, caste, disabled, minority, resident)';

  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx1') || ' ON ' || quote_ident(_tablename5) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx4') || ' ON ' || quote_ident(_tablename5) || '(supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx5') || ' ON ' || quote_ident(_tablename5) || '(awc_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx6') || ' ON ' || quote_ident(_tablename5) || '(ccs_status)';

    -- may want a double index on month and caste for aggregate  location query

  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_ccs_record SET ' ||
    'rations_21_plus_distributed = temp.rations_21_plus_distributed, ' ||
    'thr_eligible = temp.thr_eligible '
    'FROM (SELECT ' ||
      'awc_id, month, ccs_status, trimester, caste, ' ||
      'coalesce(disabled, ' || quote_nullable(_no_text) || ') as coalesce_disabled, ' ||
      'coalesce(minority, ' || quote_nullable(_no_text) || ') as coalesce_minority, ' ||
      'coalesce(resident, ' || quote_nullable(_no_text) || ') as coalesce_resident, ' ||
      'coalesce(trimester::text, ' || quote_nullable(_blank_value) || ') as coalesce_trimester, '
      'sum(thr_eligible) as thr_eligible, ' ||
      'sum(CASE WHEN num_rations_distributed >= 21 THEN 1 ELSE 0 END) as rations_21_plus_distributed ' ||
      'FROM ' || quote_ident(_ccs_record_monthly_table) || ' ' ||
      'GROUP BY awc_id, month, ccs_status, trimester, caste, coalesce_disabled, coalesce_minority, coalesce_resident) temp ' ||
    'WHERE temp.awc_id = agg_ccs_record.awc_id AND temp.month = agg_ccs_record.month AND temp.ccs_status = agg_ccs_record.ccs_status ' ||
      'AND temp.coalesce_trimester = agg_ccs_record.trimester AND temp.caste = agg_ccs_record.caste ' ||
      'AND temp.coalesce_disabled = agg_ccs_record.disabled AND temp.coalesce_minority = agg_ccs_record.minority ' ||
      'AND temp.coalesce_resident = agg_ccs_record.resident';

  --Roll up by location
  _rollup_text = 'sum(valid_in_month), ' ||
    'sum(lactating), ' ||
    'sum(pregnant), ' ||
    'sum(thr_eligible), ' ||
    'sum(rations_21_plus_distributed), ' ||
    'sum(tetanus_complete), ' ||
    'sum(delivered_in_month), ' ||
    'sum(anc1_received_at_delivery), ' ||
    'sum(anc2_received_at_delivery), ' ||
    'sum(anc3_received_at_delivery), ' ||
    'sum(anc4_received_at_delivery), ' ||
    'avg(registration_trimester_at_delivery), ' ||
    'sum(using_ifa), ' ||
    'sum(ifa_consumed_last_seven_days), ' ||
    'sum(anemic_normal), ' ||
    'sum(anemic_moderate), ' ||
    'sum(anemic_severe), ' ||
    'sum(anemic_unknown), ' ||
    'sum(extra_meal), ' ||
    'sum(resting_during_pregnancy), ' ||
    'sum(bp1_complete), ' ||
    'sum(bp2_complete), ' ||
    'sum(bp3_complete), ' ||
    'sum(pnc_complete), ' ||
    'sum(trimester_2), ' ||
    'sum(trimester_3), ' ||
    'sum(postnatal), ' ||
    'sum(counsel_bp_vid), ' ||
    'sum(counsel_preparation), ' ||
    'sum(counsel_immediate_bf), ' ||
    'sum(counsel_fp_vid), ' ||
    'sum(counsel_immediate_conception), ' ||
    'sum(counsel_accessible_postpartum_fp), ' ||
    'sum(has_aadhar_id), ';

  _rollup_text2 = 'sum(valid_all_registered_in_month), ' ||
    'sum(institutional_delivery_in_month), ' ||
    'sum(lactating_all), ' ||
    'sum(pregnant_all) ';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename4) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'ccs_status, ' ||
    'trimester, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'valid_in_month, ' ||
    'lactating, ' ||
    'pregnant, ' ||
    'thr_eligible, ' ||
    'rations_21_plus_distributed, ' ||
    'tetanus_complete, ' ||
    'delivered_in_month, ' ||
    'anc1_received_at_delivery, ' ||
    'anc2_received_at_delivery, ' ||
    'anc3_received_at_delivery, ' ||
    'anc4_received_at_delivery, ' ||
    'registration_trimester_at_delivery, ' ||
    'using_ifa, ' ||
    'ifa_consumed_last_seven_days, ' ||
    'anemic_normal, ' ||
    'anemic_moderate, ' ||
    'anemic_severe, ' ||
    'anemic_unknown, ' ||
    'extra_meal, ' ||
    'resting_during_pregnancy, ' ||
    'bp1_complete, ' ||
    'bp2_complete, ' ||
    'bp3_complete, ' ||
    'pnc_complete, ' ||
    'trimester_2, ' ||
    'trimester_3, ' ||
    'postnatal, ' ||
    'counsel_bp_vid, ' ||
    'counsel_preparation, ' ||
    'counsel_immediate_bf, ' ||
    'counsel_fp_vid, ' ||
    'counsel_immediate_conception, ' ||
    'counsel_accessible_postpartum_fp, ' ||
    'has_aadhar_id, ' ||
    'aggregation_level, ' ||
    'valid_all_registered_in_month, ' ||
    'institutional_delivery_in_month, ' ||
    'lactating_all, ' ||
    'pregnant_all ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    'ccs_status, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    _rollup_text ||
    '4, ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename5) || ' ' ||
    'GROUP BY state_id, district_id, block_id, supervisor_id, month, ccs_status)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx1') || ' ON ' || quote_ident(_tablename4) || '(state_id, district_id, block_id, supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx2') || ' ON ' || quote_ident(_tablename4) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx3') || ' ON ' || quote_ident(_tablename4) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx4') || ' ON ' || quote_ident(_tablename4) || '(supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx5') || ' ON ' || quote_ident(_tablename4) || '(ccs_status)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename3) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'ccs_status, ' ||
    'trimester, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'valid_in_month, ' ||
    'lactating, ' ||
    'pregnant, ' ||
    'thr_eligible, ' ||
    'rations_21_plus_distributed, ' ||
    'tetanus_complete, ' ||
    'delivered_in_month, ' ||
    'anc1_received_at_delivery, ' ||
    'anc2_received_at_delivery, ' ||
    'anc3_received_at_delivery, ' ||
    'anc4_received_at_delivery, ' ||
    'registration_trimester_at_delivery, ' ||
    'using_ifa, ' ||
    'ifa_consumed_last_seven_days, ' ||
    'anemic_normal, ' ||
    'anemic_moderate, ' ||
    'anemic_severe, ' ||
    'anemic_unknown, ' ||
    'extra_meal, ' ||
    'resting_during_pregnancy, ' ||
    'bp1_complete, ' ||
    'bp2_complete, ' ||
    'bp3_complete, ' ||
    'pnc_complete, ' ||
    'trimester_2, ' ||
    'trimester_3, ' ||
    'postnatal, ' ||
    'counsel_bp_vid, ' ||
    'counsel_preparation, ' ||
    'counsel_immediate_bf, ' ||
    'counsel_fp_vid, ' ||
    'counsel_immediate_conception, ' ||
    'counsel_accessible_postpartum_fp, ' ||
    'has_aadhar_id, ' ||
    'aggregation_level, ' ||
    'valid_all_registered_in_month, ' ||
    'institutional_delivery_in_month, ' ||
    'lactating_all, ' ||
    'pregnant_all ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    'ccs_status, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    _rollup_text ||
    '3, ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename4) || ' ' ||
    'GROUP BY state_id, district_id, block_id, month, ccs_status)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx1') || ' ON ' || quote_ident(_tablename3) || '(state_id, district_id, block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx2') || ' ON ' || quote_ident(_tablename3) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx3') || ' ON ' || quote_ident(_tablename3) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx4') || ' ON ' || quote_ident(_tablename3) || '(ccs_status)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename2) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'ccs_status, ' ||
    'trimester, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'valid_in_month, ' ||
    'lactating, ' ||
    'pregnant, ' ||
    'thr_eligible, ' ||
    'rations_21_plus_distributed, ' ||
    'tetanus_complete, ' ||
    'delivered_in_month, ' ||
    'anc1_received_at_delivery, ' ||
    'anc2_received_at_delivery, ' ||
    'anc3_received_at_delivery, ' ||
    'anc4_received_at_delivery, ' ||
    'registration_trimester_at_delivery, ' ||
    'using_ifa, ' ||
    'ifa_consumed_last_seven_days, ' ||
    'anemic_normal, ' ||
    'anemic_moderate, ' ||
    'anemic_severe, ' ||
    'anemic_unknown, ' ||
    'extra_meal, ' ||
    'resting_during_pregnancy, ' ||
    'bp1_complete, ' ||
    'bp2_complete, ' ||
    'bp3_complete, ' ||
    'pnc_complete, ' ||
    'trimester_2, ' ||
    'trimester_3, ' ||
    'postnatal, ' ||
    'counsel_bp_vid, ' ||
    'counsel_preparation, ' ||
    'counsel_immediate_bf, ' ||
    'counsel_fp_vid, ' ||
    'counsel_immediate_conception, ' ||
    'counsel_accessible_postpartum_fp, ' ||
    'has_aadhar_id, ' ||
    'aggregation_level, ' ||
    'valid_all_registered_in_month, ' ||
    'institutional_delivery_in_month, ' ||
    'lactating_all, ' ||
    'pregnant_all ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    'ccs_status, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    _rollup_text ||
    '2, ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename3) || ' ' ||
    'GROUP BY state_id, district_id, month, ccs_status)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx1') || ' ON ' || quote_ident(_tablename2) || '(state_id, district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx2') || ' ON ' || quote_ident(_tablename2) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx3') || ' ON ' || quote_ident(_tablename2) || '(ccs_status)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename1) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'ccs_status, ' ||
    'trimester, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'valid_in_month, ' ||
    'lactating, ' ||
    'pregnant, ' ||
    'thr_eligible, ' ||
    'rations_21_plus_distributed, ' ||
    'tetanus_complete, ' ||
    'delivered_in_month, ' ||
    'anc1_received_at_delivery, ' ||
    'anc2_received_at_delivery, ' ||
    'anc3_received_at_delivery, ' ||
    'anc4_received_at_delivery, ' ||
    'registration_trimester_at_delivery, ' ||
    'using_ifa, ' ||
    'ifa_consumed_last_seven_days, ' ||
    'anemic_normal, ' ||
    'anemic_moderate, ' ||
    'anemic_severe, ' ||
    'anemic_unknown, ' ||
    'extra_meal, ' ||
    'resting_during_pregnancy, ' ||
    'bp1_complete, ' ||
    'bp2_complete, ' ||
    'bp3_complete, ' ||
    'pnc_complete, ' ||
    'trimester_2, ' ||
    'trimester_3, ' ||
    'postnatal, ' ||
    'counsel_bp_vid, ' ||
    'counsel_preparation, ' ||
    'counsel_immediate_bf, ' ||
    'counsel_fp_vid, ' ||
    'counsel_immediate_conception, ' ||
    'counsel_accessible_postpartum_fp, ' ||
    'has_aadhar_id, ' ||
    'aggregation_level, ' ||
    'valid_all_registered_in_month, ' ||
    'institutional_delivery_in_month, ' ||
    'lactating_all, ' ||
    'pregnant_all ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    'ccs_status, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    _rollup_text ||
    '1, ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename2) || ' ' ||
    'GROUP BY state_id, month, ccs_status)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx1') || ' ON ' || quote_ident(_tablename1) || '(state_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx2') || ' ON ' || quote_ident(_tablename1) || '(ccs_status)';
END;
$BODY$
LANGUAGE plpgsql;
