-- Add columns for additional forms
ALTER TABLE agg_awc ADD COLUMN usage_num_hh_reg integer;
ALTER TABLE agg_awc ADD COLUMN usage_num_add_person integer;
ALTER TABLE agg_awc ADD COLUMN usage_num_add_pregnancy integer;