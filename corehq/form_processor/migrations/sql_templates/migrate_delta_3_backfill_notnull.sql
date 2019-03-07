UPDATE form_processor_ledgertransaction SET new_delta = delta WHERE new_delta IS NULL;
ALTER TABLE form_processor_ledgertransaction ALTER COLUMN new_delta SET NOT NULL;
