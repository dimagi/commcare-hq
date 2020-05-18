ALTER TABLE ccs_record_monthly ADD COLUMN complication_type text;
ALTER TABLE ccs_record_monthly ADD COLUMN reason_no_ifa text;
ALTER TABLE ccs_record_monthly ADD COLUMN new_ifa_tablets_total_bp INTEGER;
ALTER TABLE ccs_record_monthly ADD COLUMN new_ifa_tablets_total_pnc INTEGER;
ALTER TABLE ccs_record_monthly ADD COLUMN ifa_last_seven_days INTEGER;
