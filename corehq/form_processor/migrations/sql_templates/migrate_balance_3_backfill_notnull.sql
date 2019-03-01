UPDATE form_processor_ledgertransaction SET new_updated_balance = updated_balance;
ALTER TABLE form_processor_ledgertransaction ALTER COLUMN new_updated_balance SET NOT NULL;
