ALTER TABLE ccs_record_monthly ADD COLUMN valid_visits smallint;
ALTER TABLE agg_ccs_record ADD COLUMN valid_visits int;
ALTER TABLE agg_ccs_record ADD COLUMN expected_visits int;
