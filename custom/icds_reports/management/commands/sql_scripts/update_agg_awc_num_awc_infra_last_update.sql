CREATE OR REPLACE FUNCTION update_agg_awc_num_awc_infra_last_update(date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename1 text;
  _tablename2 text;
  _tablename3 text;
  _tablename4 text;
  _tablename5 text;
  _start_date date;
  _month_start_6m date;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _tablename1 := 'agg_awc' || '_' || _start_date || '_1';
  _tablename2 := 'agg_awc' || '_' || _start_date || '_2';
  _tablename3 := 'agg_awc' || '_' || _start_date || '_3';
  _tablename4 := 'agg_awc' || '_' || _start_date || '_4';
  _tablename5 := 'agg_awc' || '_' || _start_date || '_5';
  _month_start_6m = (_start_date + INTERVAL ' - 6 MONTHS')::DATE;

  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET num_awc_infra_last_update = ' ||
   'CASE WHEN infra_last_update_date IS NOT NULL AND ' ||
     quote_literal(_month_start_6m) || ' < infra_last_update_date THEN 1 ELSE 0 END';

  EXECUTE 'UPDATE ' || quote_ident(_tablename4) || ' agg_awc SET ' ||
    '(' ||
    'num_awc_infra_last_update, ' ||
    ')' ||
    '(SELECT ' ||
    'sum(num_awc_infra_last_update), ' ||
    'FROM ' || quote_ident(_tablename5) || ' ' ||
    'GROUP BY state_id, district_id, block_id, supervisor_id, month)';

  EXECUTE 'UPDATE ' || quote_ident(_tablename3) || ' agg_awc SET ' ||
    '(' ||
    'num_awc_infra_last_update, ' ||
    ')' ||
    '(SELECT ' ||
    'sum(num_awc_infra_last_update), ' ||
    'FROM ' || quote_ident(_tablename4) || ' ' ||
    'GROUP BY state_id, district_id, block_id, month)';

  EXECUTE 'UPDATE ' || quote_ident(_tablename2) || ' agg_awc SET ' ||
    '(' ||
    'num_awc_infra_last_update, ' ||
    ')' ||
    '(SELECT ' ||
    'sum(num_awc_infra_last_update), ' ||
    'FROM ' || quote_ident(_tablename3) || ' ' ||
    'GROUP BY state_id, district_id, month)';

  EXECUTE 'UPDATE ' || quote_ident(_tablename1) || ' agg_awc SET ' ||
    '(' ||
    'num_awc_infra_last_update, ' ||
    ')' ||
    '(SELECT ' ||
    'sum(num_awc_infra_last_update), ' ||
    'FROM ' || quote_ident(_tablename2) || ' ' ||
    'GROUP BY state_id, month)';

END;
$BODY$
LANGUAGE plpgsql;
