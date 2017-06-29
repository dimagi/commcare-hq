-- Update only for the current day
BEGIN;
	SELECT aggregate_awc_daily((current_date)::date);
COMMIT;
