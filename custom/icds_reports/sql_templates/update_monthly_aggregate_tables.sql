-- Update for each Month
-- Need to replace / change the interval
BEGIN
	SELECT profile_line('update_monthly_aggregate_tables', 'start');
COMMIT;

BEGIN;
	-- Update Months Table
	SELECT update_months_table((%(date)s)::date);
COMMIT;

BEGIN
	SELECT profile_line('update_monthly_aggregate_tables', 'update_months_table');
COMMIT;

BEGIN;
	SELECT create_new_table_for_month('child_health_monthly', (%(date)s)::date);
	SELECT insert_into_child_health_monthly((%(date)s)::date);
COMMIT;

BEGIN
	SELECT profile_line('update_monthly_aggregate_tables', 'insert_into_child_health_monthly');
COMMIT;

BEGIN;
	SELECT create_new_table_for_month('ccs_record_monthly', (%(date)s)::date);
	SELECT insert_into_ccs_record_monthly((%(date)s)::date);
COMMIT;

BEGIN
	SELECT profile_line('update_monthly_aggregate_tables', 'insert_into_ccs_record_monthly');
COMMIT;

BEGIN;
	SELECT create_new_table_for_month('daily_attendance', (%(date)s)::date);
	SELECT insert_into_daily_attendance((%(date)s)::date);
COMMIT;

BEGIN
	SELECT profile_line('update_monthly_aggregate_tables', 'insert_into_daily_attendance');
COMMIT;

BEGIN;
	SELECT create_new_aggregate_table_for_month('agg_child_health', (%(date)s)::date);
	SELECT aggregate_child_health((%(date)s)::date);
COMMIT;

BEGIN
	SELECT profile_line('update_monthly_aggregate_tables', 'aggregate_child_health');
COMMIT;

BEGIN;
	SELECT create_new_aggregate_table_for_month('agg_ccs_record', (%(date)s)::date);
	SELECT aggregate_ccs_record((%(date)s)::date);
COMMIT;

BEGIN
	SELECT profile_line('update_monthly_aggregate_tables', 'aggregate_ccs_record');
COMMIT;

BEGIN;
	SELECT create_new_aggregate_table_for_month('agg_awc', (%(date)s)::date);
	SELECT aggregate_awc_data((%(date)s)::date);
COMMIT;

BEGIN
	SELECT profile_line('update_monthly_aggregate_tables', 'aggregate_awc_data');
COMMIT;
