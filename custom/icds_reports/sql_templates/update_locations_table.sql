-- Update locations table
BEGIN;
	SELECT update_location_table();
	SELECT aggregate_location_table();
COMMIT;
