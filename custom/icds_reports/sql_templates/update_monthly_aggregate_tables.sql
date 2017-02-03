-- Update for each Month
-- Need to replace / change the interval
BEGIN;
	-- Update Months Table
	SELECT update_months_table((current_date - INTERVAL %(interval)s)::date);

	-- Setup Monthly Tables
	-- Could turn this into a script with variable for date (or for individual tables)
	SELECT create_new_table_for_month('agg_awc', (current_date - INTERVAL %(interval)s)::date);
	SELECT create_new_table_for_month('agg_ccs_record', (current_date - INTERVAL %(interval)s)::date);
	SELECT create_new_table_for_month('agg_child_health', (current_date - INTERVAL %(interval)s)::date);
	SELECT create_new_table_for_month('ccs_record_monthly', (current_date - INTERVAL %(interval)s)::date);
	SELECT create_new_table_for_month('child_health_monthly', (current_date - INTERVAL %(interval)s)::date);
	SELECT create_new_table_for_month('agg_thr_data', (current_date - INTERVAL %(interval)s)::date);
	SELECT create_new_table_for_month('daily_attendance', (current_date - INTERVAL %(interval)s)::date);

	-- Copy Data Into Monthly Tables
	SELECT insert_into_child_health_monthly((current_date - INTERVAL %(interval)s)::date);
	SELECT insert_into_ccs_record_monthly((current_date - INTERVAL %(interval)s)::date);
	SELECT insert_into_daily_attendance((current_date - INTERVAL %(interval)s)::date);

	-- Aggregate data into monthly tables
	SELECT aggregate_child_health((current_date - INTERVAL %(interval)s)::date);
	SELECT aggregate_ccs_record((current_date - INTERVAL %(interval)s)::date);
	SELECT aggregate_thr_data((current_date - INTERVAL %(interval)s)::date);
	SELECT aggregate_awc_data((current_date - INTERVAL %(interval)s)::date);

COMMIT;
