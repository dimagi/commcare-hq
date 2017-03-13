ALTER TABLE child_health_monthly ADD COLUMN recorded_height decimal;
ALTER TABLE agg_child_health ADD COLUMN has_aadhar_id integer;
ALTER TABLE agg_ccs_record ADD COLUMN has_aadhar_id integer;