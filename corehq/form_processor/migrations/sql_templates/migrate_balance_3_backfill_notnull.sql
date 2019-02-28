UPDATE form_processor_ledgertransaction SET new_updated_balance = updated_balance WHERE new_updated_balance IS NULL;
ALTER TABLE form_processor_ledgertransaction ALTER COLUMN new_updated_balance SET NOT NULL;
