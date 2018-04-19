-- Update only for the current day
BEGIN;
	SELECT aggregate_awc_daily((%(date)s)::date);
COMMIT;
