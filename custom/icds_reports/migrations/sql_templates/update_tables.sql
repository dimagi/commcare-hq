-- Remove not null constraint on aggregated columns (data is sometimes null)
ALTER TABLE agg_child_health ALTER COLUMN age_tranche DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN disabled DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN resident DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN caste DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN minority DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN gender DROP NOT NULL;
ALTER TABLE agg_ccs_record ALTER COLUMN registration_trimester_at_delivery DROP NOT NULL;
ALTER TABLE agg_ccs_record ALTER COLUMN disabled DROP NOT NULL;
ALTER TABLE agg_ccs_record ALTER COLUMN resident DROP NOT NULL;
ALTER TABLE agg_ccs_record ALTER COLUMN caste DROP NOT NULL;
ALTER TABLE agg_ccs_record ALTER COLUMN minority DROP NOT NULL;
