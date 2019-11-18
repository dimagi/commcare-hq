-- Switch columns
ALTER TABLE form_processor_ledgertransaction ALTER COLUMN delta DROP NOT NULL;
ALTER TABLE form_processor_ledgertransaction RENAME COLUMN delta TO old_delta;
ALTER TABLE form_processor_ledgertransaction RENAME COLUMN new_delta TO delta;
ALTER TABLE form_processor_ledgertransaction DROP COLUMN old_delta;

-- Clean up
DROP TRIGGER IF EXISTS copy_delta_trigger ON form_processor_ledgertransaction;
DROP FUNCTION IF EXISTS copy_delta();
