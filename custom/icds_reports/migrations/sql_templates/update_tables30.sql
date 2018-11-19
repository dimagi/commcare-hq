DROP VIEW IF EXISTS agg_ccs_record_monthly CASCADE;
ALTER TABLE agg_ccs_record ALTER COLUMN expected_visits type decimal;
