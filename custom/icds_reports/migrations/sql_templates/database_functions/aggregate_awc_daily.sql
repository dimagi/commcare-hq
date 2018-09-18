-- Aggregate a single daily  for the AWC
-- Depends on generation of the agg_awc table
CREATE OR REPLACE FUNCTION aggregate_awc_daily(date) RETURNS VOID AS
$BODY$
DECLARE
  _table_date date;
  _current_month date;
  _tablename text;
  _table_columns text;
    _daily_attendance_tablename text;
    _all_text text;
    _null_value text;
    _rollup_text text;
    _rollup_text_2 text;
BEGIN
  _table_date = ($1)::DATE;
  _current_month = date_trunc('MONTH', $1)::DATE;
  _tablename = 'agg_awc_daily' || '_' || _table_date;
  _all_text = 'All';
  _null_value = NULL;

  -- Explicitly define the table columns for use in updates and aggregation
  _table_columns = '' ||
      'state_id, ' ||
      'district_id, ' ||
      'block_id, ' ||
      'supervisor_id, ' ||
      'awc_id, ' ||
      'aggregation_level, ' ||
      'date, ' ||
      'cases_household, ' ||
      'cases_person, ' ||
      'cases_person_all, ' ||
      'cases_person_has_aadhaar, ' ||
      'cases_person_beneficiary, ' ||
      'cases_child_health, ' ||
      'cases_child_health_all, ' ||
      'cases_ccs_pregnant, ' ||
      'cases_ccs_pregnant_all, ' ||
      'cases_ccs_lactating, ' ||
      'cases_ccs_lactating_all, ' ||
      'cases_person_adolescent_girls_11_14, ' ||
      'cases_person_adolescent_girls_15_18, ' ||
      'cases_person_adolescent_girls_11_14_all, ' ||
      'cases_person_adolescent_girls_15_18_all, ' ||
      'daily_attendance_open, ' ||
      'num_awcs, ' ||
      'num_launched_states, ' ||
      'num_launched_districts, ' ||
      'num_launched_blocks, ' ||
      'num_launched_supervisors, ' ||
      'num_launched_awcs, ' ||
      'cases_person_has_aadhaar_v2, ' ||
      'cases_person_beneficiary_v2 ';

  -- DROP and create daily table
  EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename);
  EXECUTE 'CREATE TABLE ' || quote_ident(_tablename) || '(' ||
        'CHECK ( date = DATE ' || quote_literal(_table_date) || ' )' ||
      ') INHERITS (agg_awc_daily)';

  -- Copy from the current month agg_awc table (skipping daily_attendance_open which will be a separate query)
  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
      '( '|| _table_columns || ') '
       '(SELECT ' ||
          'state_id, ' ||
            'district_id, ' ||
            'block_id, ' ||
            'supervisor_id, ' ||
            'awc_id, ' ||
            'aggregation_level, ' ||
            quote_literal(_table_date) || ', ' ||
            'cases_household, ' ||
            'cases_person, ' ||
            'cases_person_all, ' ||
            'cases_person_has_aadhaar, ' ||
            'cases_person_beneficiary, ' ||
            'cases_child_health, ' ||
            'cases_child_health_all, ' ||
            'cases_ccs_pregnant, ' ||
            'cases_ccs_pregnant_all, ' ||
            'cases_ccs_lactating, ' ||
            'cases_ccs_lactating_all, ' ||
            'cases_person_adolescent_girls_11_14, ' ||
            'cases_person_adolescent_girls_15_18, ' ||
            'cases_person_adolescent_girls_11_14_all, ' ||
            'cases_person_adolescent_girls_15_18_all, ' ||
            '0, ' ||
            'num_awcs, ' ||
            'num_launched_states, ' ||
            'num_launched_districts, ' ||
            'num_launched_blocks, ' ||
            'num_launched_supervisors, ' ||
            'num_launched_awcs, ' ||
            'cases_person_has_aadhaar_v2, ' ||
            'cases_person_beneficiary_v2 ' ||
         'FROM agg_awc WHERE aggregation_level = 5 AND month = ' || quote_literal(_current_month) ||
         ')';

  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx2') || ' ON ' || quote_ident(_tablename) || '(date)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx3') || ' ON ' || quote_ident(_tablename) || '(awc_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx4') || ' ON ' || quote_ident(_tablename) || '(supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx5') || ' ON ' || quote_ident(_tablename) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx6') || ' ON ' || quote_ident(_tablename) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx7') || ' ON ' || quote_ident(_tablename) || '(aggregation_level)';

  -- Aggregate daily attendance table.
  EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
    'daily_attendance_open = ut.daily_attendance_open ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'pse_date, ' ||
    'sum(awc_open_count) AS daily_attendance_open ' ||
    'FROM daily_attendance WHERE pse_date = ' || quote_literal(_table_date) || ' ' ||
    'GROUP BY awc_id, pse_date) ut ' ||
  'WHERE ut.pse_date = agg_awc.date AND ut.awc_id = agg_awc.awc_id';

  -- Roll Up by Location
  _rollup_text =   'sum(cases_household), ' ||
    'sum(cases_person), ' ||
    'sum(cases_person_all), ' ||
    'sum(cases_person_has_aadhaar), ' ||
    'sum(cases_person_beneficiary), ' ||
    'sum(cases_child_health), ' ||
    'sum(cases_child_health_all), ' ||
    'sum(cases_ccs_pregnant), ' ||
    'sum(cases_ccs_pregnant_all), ' ||
    'sum(cases_ccs_lactating), ' ||
    'sum(cases_ccs_lactating_all), ' ||
    'sum(cases_person_adolescent_girls_11_14), ' ||
    'sum(cases_person_adolescent_girls_15_18), ' ||
    'sum(cases_person_adolescent_girls_11_14_all), ' ||
    'sum(cases_person_adolescent_girls_15_18_all), ' ||
    'sum(daily_attendance_open), ' ||
    'sum(num_awcs), ';

  _rollup_text_2 = 'sum(cases_person_has_aadhaar_v2), ' ||
    'sum(cases_person_beneficiary_v2) ';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
      '( '|| _table_columns || ') '
      '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    quote_literal(_all_text) || ', ' ||
    '4, ' ||
    'date, ' ||
    _rollup_text ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
    'sum(num_launched_awcs), ' ||
    _rollup_text_2 ||
    'FROM ' || quote_ident(_tablename) || ' ' ||
    'WHERE aggregation_level = 5 ' ||
    'GROUP BY state_id, district_id, block_id, supervisor_id, date)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
      '( '|| _table_columns || ') '
      '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    '3, ' ||
    'date, ' ||
    _rollup_text ||
    'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
    'sum(num_launched_supervisors), ' ||
    'sum(num_launched_awcs), ' ||
    _rollup_text_2 ||
    'FROM ' || quote_ident(_tablename) || ' ' ||
    'WHERE aggregation_level = 4 ' ||
    'GROUP BY state_id, district_id, block_id, date)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
      '( '|| _table_columns || ') '
      '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    '2, ' ||
    'date, ' ||
    _rollup_text ||
    'CASE WHEN (sum(num_launched_blocks) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_blocks) > 0) THEN 1 ELSE 0 END, ' ||
    'sum(num_launched_blocks), ' ||
    'sum(num_launched_supervisors), ' ||
    'sum(num_launched_awcs), ' ||
    _rollup_text_2 ||
    'FROM ' || quote_ident(_tablename) || ' ' ||
    'WHERE aggregation_level = 3 ' ||
    'GROUP BY state_id, district_id, date)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
      '( '|| _table_columns || ') '
      '(SELECT ' ||
    'state_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    '1, ' ||
    'date, ' ||
    _rollup_text ||
    'CASE WHEN (sum(num_launched_districts) > 0) THEN 1 ELSE 0 END, ' ||
    'sum(num_launched_districts), ' ||
    'sum(num_launched_blocks), ' ||
    'sum(num_launched_supervisors), ' ||
    'sum(num_launched_awcs), ' ||
    _rollup_text_2 ||
    'FROM ' || quote_ident(_tablename) || ' ' ||
    'WHERE aggregation_level = 2 ' ||
    'GROUP BY state_id, date)';

END;
$BODY$
LANGUAGE plpgsql;