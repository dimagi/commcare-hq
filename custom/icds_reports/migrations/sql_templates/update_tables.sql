-- Remove not null constraint on age tranche (data is incomplete)
ALTER TABLE agg_child_health ALTER COLUMN age_tranche DROP NOT NULL;
