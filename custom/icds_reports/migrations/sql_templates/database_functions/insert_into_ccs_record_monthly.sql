
-- Copy into ccs_record_monthly
CREATE OR REPLACE FUNCTION insert_into_ccs_record_monthly(date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename text;
  _ucr_ccs_record_table text;
  _ucr_pregnant_tasks_table text;
  _agg_thr_form_table text;
  _start_date date;
  _end_date date;
  _ucr_ccs_record_cases_table text;
  _agg_bp_form_table text;
  _agg_pnc_form_table text;
  _agg_delivery_form_table text;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _end_date = (date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 SECOND')::DATE;
  _tablename := 'ccs_record_monthly' || '_' || _start_date;
  _agg_thr_form_table := 'icds_dashboard_ccs_record_thr_forms';
  _agg_bp_form_table := 'icds_dashboard_ccs_record_bp_forms';
  _agg_pnc_form_table := 'icds_dashboard_ccs_record_postnatal_forms';
  _agg_delivery_form_table := 'icds_dashboard_ccs_record_delivery_forms';
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('ccs_record_monthly') INTO _ucr_ccs_record_table;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('pregnant_tasks') INTO _ucr_pregnant_tasks_table;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('ccs_record_list') INTO _ucr_ccs_record_cases_table;

  EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || ' ' ||
    '(' ||
    'awc_id, ' ||
    'case_id, ' ||
    'month, ' ||
    'age_in_months, ' ||
    'ccs_status, ' ||
    'open_in_month, ' ||
    'alive_in_month, ' ||
    'trimester, ' ||
    'num_rations_distributed, ' ||
    'thr_eligible, ' ||
    'tetanus_complete, ' ||
    'delivered_in_month, ' ||
    'anc1_received_at_delivery, ' ||
    'anc2_received_at_delivery, ' ||
    'anc3_received_at_delivery, ' ||
    'anc4_received_at_delivery, ' ||
    'registration_trimester_at_delivery, ' ||
    'using_ifa, ' ||
    'ifa_consumed_last_seven_days, ' ||
    'anemic_severe, ' ||
    'anemic_moderate, ' ||
    'anemic_normal, ' ||
    'anemic_unknown, ' ||
    'extra_meal, ' ||
    'resting_during_pregnancy, ' ||
    'bp_visited_in_month, ' ||
    'pnc_visited_in_month, ' ||
    'trimester_2, ' ||
    'trimester_3, ' ||
    'counsel_immediate_bf, ' ||
    'counsel_bp_vid, ' ||
    'counsel_preparation, ' ||
    'counsel_fp_vid, ' ||
    'counsel_immediate_conception, ' ||
    'counsel_accessible_postpartum_fp, ' ||
    'bp1_complete, ' ||
    'bp2_complete, ' ||
    'bp3_complete, ' ||
    'pnc_complete, ' ||
    'postnatal, ' ||
    'has_aadhar_id, ' ||
    'counsel_fp_methods, ' ||
    'pregnant, ' ||
    'pregnant_all, ' ||
    'lactating, ' ||
    'lactating_all, ' ||
    'institutional_delivery_in_month, ' ||
    'add, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'valid_in_month ' ||
    ')' ||
    '(SELECT ' ||
    'awc_id, ' ||
    'case_id, ' ||
    'month, ' ||
    'age_in_months, ' ||
    'ccs_status, ' ||
    'open_in_month, ' ||
    'alive_in_month, ' ||
    'trimester, ' ||
    '0, ' ||
    'thr_eligible, ' ||
    'tetanus_complete, ' ||
    'delivered_in_month, ' ||
    'anc1_received_at_delivery, ' ||
    'anc2_received_at_delivery, ' ||
    'anc3_received_at_delivery, ' ||
    'anc4_received_at_delivery, ' ||
    'registration_trimester_at_delivery, ' ||
    'using_ifa, ' ||
    'ifa_consumed_last_seven_days, ' ||
    'anemic_severe, ' ||
    'anemic_moderate, ' ||
    'anemic_normal, ' ||
    'anemic_unknown, ' ||
    'extra_meal, ' ||
    'resting_during_pregnancy, ' ||
    'bp_visited_in_month, ' ||
    'NULL, ' ||
    'trimester_2, ' ||
    'trimester_3, ' ||
    'counsel_immediate_bf, ' ||
    'counsel_bp_vid, ' ||
    'counsel_preparation, ' ||
    'counsel_bp_vid, ' ||
    'counsel_immediate_conception, ' ||
    'counsel_accessible_postpartum_fp, ' ||
    'bp1_complete, ' ||
    'bp2_complete, ' ||
    'bp3_complete, ' ||
    'pnc_complete, ' ||
    'postnatal, ' ||
    'has_aadhar_id, ' ||
    'NULL, ' ||
    'pregnant, ' ||
    'pregnant_all, ' ||
    'lactating, ' ||
    'lactating_all, ' ||
    'institutional_delivery_in_month, ' ||
    'add, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'valid_in_month ' ||
    'FROM ' || quote_ident(_ucr_ccs_record_table) || ' WHERE month = ' || quote_literal(_start_date) || ')';

    EXECUTE 'CREATE INDEX ON ' || quote_ident(_tablename) || '(case_id)';

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' ccs_monthly SET ' ||
      'anc_in_month =  (' ||
        '(CASE WHEN ut.due_list_date_anc_1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END) + ' ||
        '(CASE WHEN ut.due_list_date_anc_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END) + ' ||
        '(CASE WHEN ut.due_list_date_anc_3 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END) + ' ||
        '(CASE WHEN ut.due_list_date_anc_4 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END)' ||
      '), ' ||
       'anc_1 = ut.due_list_date_anc_1, ' ||
       'anc_2 = ut.due_list_date_anc_2, ' ||
       'anc_3 = ut.due_list_date_anc_3, ' ||
       'anc_4 = ut.due_list_date_anc_4, ' ||
       'tt_1 = ut.due_list_date_tt_1, ' ||
       'tt_2 = ut.due_list_date_tt_2 ' ||
    'FROM ' || quote_ident(_ucr_pregnant_tasks_table) || ' ut ' ||
    'WHERE ccs_monthly.case_id = ut.ccs_record_case_id';

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' ccs_monthly SET ' ||
      'num_rations_distributed = CASE WHEN ccs_monthly.thr_eligible = 1 THEN COALESCE(agg.days_ration_given_mother, 0) ELSE NULL END ' ||
    'FROM ' || quote_ident(_agg_thr_form_table) || ' agg ' ||
    'WHERE ccs_monthly.case_id = agg.case_id AND ccs_monthly.valid_in_month = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' ccs_monthly SET ' ||
    'immediate_breastfeeding = agg.immediate_breastfeeding, ' ||
    'anemia = agg.anemia, ' ||
    'eating_extra = agg.eating_extra, ' ||
    'resting = agg.resting, ' ||
    'anc_weight = agg.anc_weight, ' ||
    'anc_blood_pressure = agg.anc_blood_pressure, ' ||
    'bp_sys = agg.bp_sys, ' ||
    'bp_dia = agg.bp_dia, ' ||
    'anc_hemoglobin = agg.anc_hemoglobin, ' ||
    'bleeding = agg.bleeding, ' ||
    'swelling = agg.swelling, ' ||
    'blurred_vision = agg.blurred_vision, ' ||
    'convulsions = agg.convulsions, ' ||
    'rupture = agg.rupture, ' ||
    'home_visit_date = agg.latest_time_end_processed::DATE ' ||
    'FROM ' || quote_ident(_agg_bp_form_table) || ' agg ' ||
    'WHERE ccs_monthly.case_id = agg.case_id AND ccs_monthly.valid_in_month = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' ccs_monthly SET ' ||
    'is_ebf = agg.is_ebf ' ||
    'FROM ' || quote_ident(_agg_pnc_form_table) || ' agg ' ||
    'WHERE ccs_monthly.case_id = agg.case_id AND ccs_monthly.valid_in_month = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' ccs_monthly SET ' ||
    'breastfed_at_birth = agg.breastfed_at_birth ' ||
    'FROM ' || quote_ident(_agg_delivery_form_table) || ' agg ' ||
    'WHERE ccs_monthly.case_id = agg.case_id AND ccs_monthly.valid_in_month = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' ccs_monthly SET ' ||
       'person_name = case_list.person_name, ' ||
       'edd = case_list.edd, ' ||
       'delivery_nature = case_list.delivery_nature, ' ||
       'mobile_number = case_list.mobile_number, ' ||
       'preg_order = case_list.preg_order, ' ||
       'num_pnc_visits = case_list.num_pnc_visits ' ||
    'FROM ' || quote_ident(_ucr_ccs_record_cases_table) || ' case_list ' ||
    'WHERE ccs_monthly.case_id = case_list.case_id and ccs_monthly.month = ' || quote_literal(_start_date);

    EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id, case_id)';

END;
$BODY$
LANGUAGE plpgsql;
