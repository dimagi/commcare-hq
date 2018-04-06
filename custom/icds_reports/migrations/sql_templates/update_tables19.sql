ALTER TABLE awc_location ADD COLUMN aww_name text;
ALTER TABLE awc_location ADD COLUMN contact_phone_number text;
ALTER TABLE agg_awc ADD COLUMN num_anc_visits integer;
ALTER TABLE agg_awc ADD COLUMN num_children_immunized integer;
ALTER TABLE ccs_record_monthly ADD COLUMN anc_in_month smallint;
ALTER TABLE child_health_monthly ADD COLUMN immunization_in_month smallint;
