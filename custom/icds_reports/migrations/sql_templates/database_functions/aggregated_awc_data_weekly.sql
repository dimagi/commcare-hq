-- Aggregate a single table for the AWC
-- Depends on generation of other tables
CREATE OR REPLACE FUNCTION update_aggregate_awc_data(date) RETURNS VOID AS
$BODY$
DECLARE
  _start_date date;
  _end_date date;
  _previous_month_date date;

  _ccs_record_tablename text;
  _ccs_record_monthly_tablename text;
  _child_health_monthly_tablename text;
  _daily_attendance_tablename text;
  _awc_location_tablename text;
  _usage_tablename text;
  _infra_tablename text;
  _household_tablename text;
  _person_tablename text;
  _all_text text;
  _null_value text;
  _rollup_text text;
  _rollup_text2 text;
  _yes_text text;
  _no_text text;
  _female text;
  _month_start_6m date;
  _month_end_6yr date;
  _month_start_11yr date;
  _month_end_11yr date;
  _month_start_15yr date;
  _month_end_15yr date;
  _month_start_18yr date;
  _month_end_49yr date;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _end_date = (date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 day')::DATE;
  _previous_month_date = (date_trunc('MONTH', _start_date) + INTERVAL '- 1 MONTH')::DATE;
  _month_start_6m = (_start_date + INTERVAL ' - 6 MONTHS')::DATE;
  _month_end_6yr = (_end_date + INTERVAL ' - 6 YEAR')::DATE;
  _month_start_11yr = (_start_date + INTERVAL ' - 11 YEAR')::DATE;
  _month_end_11yr = (_end_date + INTERVAL ' - 11 YEAR')::DATE;
  _month_start_15yr = (_start_date + INTERVAL ' - 15 YEAR')::DATE;
  _month_end_15yr = (_end_date + INTERVAL ' - 15 YEAR')::DATE;
  _month_start_18yr = (_start_date + INTERVAL ' - 18 YEAR')::DATE;
  _month_end_49yr = (_end_date + INTERVAL ' - 49 YEAR')::DATE;
  _all_text = 'All';
  _null_value = NULL;
  _yes_text = 'yes';
  _no_text = 'no';
  _female = 'F';
  _ccs_record_tablename := 'agg_ccs_record';
  _ccs_record_monthly_tablename := 'ccs_record_monthly' || '_' || _start_date;
  _child_health_monthly_tablename := 'child_health_monthly' || '_' || _start_date;
  _daily_attendance_tablename := 'daily_attendance' || '_' || _start_date;
  _infra_tablename := 'icds_dashboard_infrastructure_forms';

  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('usage') INTO _usage_tablename;


  -- Aggregate data from usage table
  EXECUTE 'UPDATE  agg_awc SET ' ||
    'usage_num_hh_reg = ut.usage_num_hh_reg, ' ||
    'is_launched = ut.is_launched, ' ||
    'num_launched_states = ut.num_launched_awcs, ' ||
    'num_launched_districts = ut.num_launched_awcs, ' ||
    'num_launched_blocks = ut.num_launched_awcs, ' ||
    'num_launched_supervisors = ut.num_launched_awcs, ' ||
    'num_launched_awcs = ut.num_launched_awcs, ' ||
    'usage_awc_num_active = ut.usage_awc_num_active, ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'month, ' ||
    'sum(add_household) AS usage_num_hh_reg, ' ||
    'CASE WHEN sum(add_household) > 0 THEN ' || quote_literal(_yes_text) || ' ELSE ' || quote_literal(_no_text) || ' END as is_launched, '
    'CASE WHEN sum(add_household) > 0 THEN 1 ELSE 0 END as num_launched_awcs, '
    'CASE WHEN (sum(due_list_ccs) + sum(due_list_child) + sum(pse) + sum(gmp) + sum(thr) + sum(home_visit) + sum(add_pregnancy) + sum(add_household)) >= 15 THEN 1 ELSE 0 END AS usage_awc_num_active, ' ||
    'FROM ' || quote_ident(_usage_tablename) || ' ' ||
    'WHERE month <= ' || quote_literal(_start_date) || ' GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month <= agg_awc.month AND ut.awc_id = agg_awc.awc_id AND aggregation_level=5 '||
  'AND agg_awc.num_launched_awcs = 0 AND ut.num_launched_awcs != 0';




  -- Aggregate data from usage table
  EXECUTE 'UPDATE  agg_awc SET ' ||
    'usage_num_hh_reg = ut.usage_num_hh_reg, ' ||
    'num_launched_states = ut.num_launched_supervisors, ' ||
    'num_launched_districts = ut.num_launched_supervisors, ' ||
    'num_launched_blocks = ut.num_launched_supervisors, ' ||
    'num_launched_supervisors = ut.num_launched_supervisors, ' ||
    'num_launched_awcs = ut.sum_num_launched_awcs, ' ||
    'usage_awc_num_active = ut.usage_awc_num_active, ' ||
  'FROM (SELECT ' ||
    'supervisor_id'
    'awc_id, ' ||
    'month, ' ||
    'usage_num_hh_reg, ' ||
    'is_launched, ' ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END as num_launched_supervisors, '||
    'sum(num_launched_awcs) as sum_num_launched_awcs, '||
    'usage_awc_num_active, ' ||
    'FROM agg_awc  ' ||
    'WHERE aggregation_level=5 '||
    'GROUP BY state_id, district_id, block_id, supervisor_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.supervisor_id = agg_awc.supervisor_id AND aggregation_level=4' ;


  -- Aggregate data from usage table
  EXECUTE 'UPDATE  agg_awc SET ' ||
    'usage_num_hh_reg = ut.usage_num_hh_reg, ' ||
    'num_launched_states = ut.num_launched_blocks, ' ||
    'num_launched_districts = ut.num_launched_blocks, ' ||
    'num_launched_blocks = ut.num_launched_blocks, ' ||
    'num_launched_supervisors = ut.sum_num_launched_supervisors, ' ||
    'num_launched_awcs = ut.sum_num_launched_awcs, ' ||
    'usage_awc_num_active = ut.usage_awc_num_active, ' ||
  'FROM (SELECT ' ||
    'block_id' ||
    'month, ' ||
    'usage_num_hh_reg, ' ||
    'is_launched, ' ||
    'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END as num_launched_blocks, '||
    'sum(num_launched_supervisors) as sum_num_launched_supervisors, '||
    'sum(num_launched_awcs) as sum_num_launched_awcs, '||
    'usage_awc_num_active, ' ||
    'FROM agg_awc  ' ||
    'WHERE aggregation_level=4 '||
    'GROUP BY state_id, district_id, block_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.block_id = agg_awc.block_id AND aggregation_level=3' ;


  -- Aggregate data from usage table
  EXECUTE 'UPDATE  agg_awc SET ' ||
    'usage_num_hh_reg = ut.usage_num_hh_reg, ' ||
    'num_launched_states = ut.num_launched_districts, ' ||
    'num_launched_districts = ut.num_launched_districts, ' ||
    'num_launched_blocks = ut.sum_num_launched_blocks, ' ||
    'num_launched_supervisors = ut.sum_num_launched_supervisors, ' ||
    'num_launched_awcs = ut.sum_num_launched_awcs, ' ||
    'usage_awc_num_active = ut.usage_awc_num_active, ' ||
  'FROM (SELECT ' ||
    'district_id' ||
    'month, ' ||
    'usage_num_hh_reg, ' ||
    'is_launched, ' ||
    'CASE WHEN (sum(num_launched_blocks) > 0) THEN 1 ELSE 0 END as num_launched_districts, ' ||
    'sum(num_launched_blocks) as sum_num_launched_blocks, ' ||
    'sum(num_launched_supervisors) as sum_num_launched_supervisors, '||
    'sum(num_launched_awcs) as sum_num_launched_awcs, '||
    'usage_awc_num_active, ' ||
    'FROM agg_awc  ' ||
    'WHERE aggregation_level=3 '||
    'GROUP BY state_id, district_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.district_id = agg_awc.district_id AND aggregation_level=2' ;



  -- Aggregate data from usage table
  EXECUTE 'UPDATE  agg_awc SET ' ||
    'usage_num_hh_reg = ut.usage_num_hh_reg, ' ||
    'num_launched_states = ut.num_launched_state, ' ||
    'num_launched_districts = ut.sum_num_launched_districts, ' ||
    'num_launched_blocks = ut.sum_num_launched_blocks, ' ||
    'num_launched_supervisors = ut.sum_num_launched_supervisors, ' ||
    'num_launched_awcs = ut.sum_num_launched_awcs, ' ||
    'usage_awc_num_active = ut.usage_awc_num_active, ' ||
  'FROM (SELECT ' ||
    'state_id' ||
    'month, ' ||
    'usage_num_hh_reg, ' ||
    'is_launched, ' ||
    'CASE WHEN (sum(num_launched_districts) > 0) THEN 1 ELSE 0 END as num_launched_state, ' ||
    'sum(num_launched_districts) as sum_num_launched_districts, ' ||
    'sum(num_launched_blocks) as sum_num_launched_blocks, ' ||
    'sum(num_launched_supervisors) as sum_num_launched_supervisors, '||
    'sum(num_launched_awcs) as sum_num_launched_awcs, '||
    'usage_awc_num_active, ' ||
    'FROM agg_awc  ' ||
    'WHERE aggregation_level=2 '||
    'GROUP BY state_id,month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.state_id = agg_awc.state_id AND aggregation_level=1' ;



END;
$BODY$
LANGUAGE plpgsql;
