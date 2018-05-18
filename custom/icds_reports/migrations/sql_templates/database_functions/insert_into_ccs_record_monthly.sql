
-- Copy into ccs_record_monthly
CREATE OR REPLACE FUNCTION insert_into_ccs_record_monthly(date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename text;
  _ucr_ccs_record_table text;
  _ucr_pregnant_tasks_table text;
  _start_date date;
  _end_date date;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _end_date = (date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 SECOND')::DATE;
  _tablename := 'ccs_record_monthly' || '_' || _start_date;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('ccs_record_monthly') INTO _ucr_ccs_record_table;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('pregnant_tasks') INTO _ucr_pregnant_tasks_table;

  EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
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
    'counsel_bp_vid, ' ||
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
    'add ' ||
    'FROM ' || quote_ident(_ucr_ccs_record_table) || ' WHERE month = ' || quote_literal(_start_date) || ')';

    EXECUTE 'CREATE INDEX ON ' || quote_ident(_tablename) || '(case_id)';

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' ccs_monthly SET ' ||
      'anc_in_month =  (' ||
        '(CASE WHEN ut.due_list_date_anc_1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END) + ' ||
        '(CASE WHEN ut.due_list_date_anc_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END) + ' ||
        '(CASE WHEN ut.due_list_date_anc_3 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END) + ' ||
        '(CASE WHEN ut.due_list_date_anc_4 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END)' ||
      ') ' ||
    'FROM ' || quote_ident(_ucr_pregnant_tasks_table) || ' ut ' ||
    'WHERE ccs_monthly.case_id = ut.ccs_record_case_id';

    EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id, case_id)';
END;
$BODY$
LANGUAGE plpgsql;
