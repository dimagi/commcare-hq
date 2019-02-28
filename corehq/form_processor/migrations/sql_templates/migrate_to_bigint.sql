-- Migrate delta and updated_balance columns to bigint without locking table

-- Create bigint_delta column, copy data from delta column, and then rename
ALTER TABLE form_processor_ledgertransaction ADD COLUMN bigint_delta BIGINT;
UPDATE form_processor_ledgertransaction SET bigint_delta = delta;
ALTER TABLE form_processor_ledgertransaction ALTER COLUMN bigint_delta SET NOT NULL;
ALTER TABLE form_processor_ledgertransaction DROP COLUMN delta;
ALTER TABLE form_processor_ledgertransaction RENAME COLUMN bigint_delta TO delta;

-- Create bigint_updated_balance column, copy data from updated_balance column, and then rename
ALTER TABLE form_processor_ledgertransaction ADD COLUMN bigint_updated_balance BIGINT;
UPDATE form_processor_ledgertransaction SET bigint_updated_balance = updated_balance;
ALTER TABLE form_processor_ledgertransaction ALTER COLUMN bigint_updated_balance SET NOT NULL;
ALTER TABLE form_processor_ledgertransaction DROP COLUMN updated_balance;
ALTER TABLE form_processor_ledgertransaction RENAME COLUMN bigint_updated_balance TO updated_balance;
