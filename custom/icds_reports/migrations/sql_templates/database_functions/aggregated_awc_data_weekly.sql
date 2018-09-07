-- Update the aggregated awc data based on previous 6 months
CREATE OR REPLACE FUNCTION update_aggregate_awc_data(date) RETURNS VOID AS
$BODY$
DECLARE
  _start_date date;
  _usage_tablename text;
  _all_text text;
  _null_value text;
  _yes_text text;
  _no_text text;
  _month_start_6m date;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _month_start_6m = (_start_date + INTERVAL ' - 6 MONTHS')::DATE;
  _all_text = 'All';
  _null_value = NULL;
  _yes_text = 'yes';
  _no_text = 'no';

  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('usage') INTO _usage_tablename;

  -- Update data from usage table from last 6 months
  -- this will update data in agg_awc child tables https://www.postgresql.org/docs/9.2/static/ddl-inherit.html
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
    'WHERE month >= ' || quote_literal(__month_start_6m) || ' GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month <= agg_awc.month AND ut.awc_id = agg_awc.awc_id AND aggregation_level=5 '||
  'AND agg_awc.num_launched_awcs = 0 AND ut.num_launched_awcs != 0';


  -- Rolling up the aggregation to supervisor level
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
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END as num_launched_supervisors, '||
    'sum(num_launched_awcs) as sum_num_launched_awcs, '||
    'usage_awc_num_active, ' ||
    'FROM agg_awc  ' ||
    'WHERE aggregation_level=5 AND month>=' || quote_literal(__month_start_6m) || ' ' ||
    'GROUP BY state_id, district_id, block_id, supervisor_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.supervisor_id = agg_awc.supervisor_id AND aggregation_level=4' ;


  -- Rolling up the aggregation to block level
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
    'WHERE aggregation_level=4 AND month>='|| quote_literal(__month_start_6m) || ' ' ||
    'GROUP BY state_id, district_id, block_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.block_id = agg_awc.block_id AND aggregation_level=3' ;


  -- Rolling up the aggregation to district level
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
    'WHERE aggregation_level=3 AND month>='|| quote_literal(__month_start_6m) || ' ' ||
    'GROUP BY state_id, district_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.district_id = agg_awc.district_id AND aggregation_level=2' ;


  -- Rolling up the aggregation to state level
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
    'WHERE aggregation_level=2 AND month>='|| quote_literal(__month_start_6m) || ' ' ||
    'GROUP BY state_id,month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.state_id = agg_awc.state_id AND aggregation_level=1' ;


END;
$BODY$
LANGUAGE plpgsql;
