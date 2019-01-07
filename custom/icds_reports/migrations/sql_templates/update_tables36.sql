ALTER TABLE ccs_record_monthly ADD COLUMN date_death date;
ALTER TABLE ccs_record_monthly ADD COLUMN person_case_id text;
ALTER TABLE child_health_monthly ADD COLUMN date_death date;
ALTER TABLE child_health_monthly ADD COLUMN mother_case_id text;