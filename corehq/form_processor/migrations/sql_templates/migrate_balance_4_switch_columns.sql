ALTER TABLE form_processor_ledgertransaction ALTER COLUMN updated_balance DROP NOT NULL;
ALTER TABLE form_processor_ledgertransaction RENAME COLUMN updated_balance TO old_updated_balance;
ALTER TABLE form_processor_ledgertransaction RENAME COLUMN new_updated_balance TO updated_balance;
ALTER TABLE form_processor_ledgertransaction DROP COLUMN old_updated_balance;

DROP TRIGGER IF EXISTS copy_balance_trigger ON form_processor_ledgertransaction;
DROP FUNCTION IF EXISTS copy_balance();
