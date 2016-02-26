DROP FUNCTION IF EXISTS save_ledger_values(TEXT[], form_processor_ledgervalue[]);

CREATE FUNCTION save_ledger_values(case_ids TEXT[], ledger_values form_processor_ledgervalue[]) RETURNS VOID AS $$
DECLARE
    ledger_value form_processor_ledgervalue;
BEGIN
    FOREACH ledger_value IN ARRAY ledger_values
    LOOP
        IF ledger_value.id IS NOT NULL THEN
            UPDATE form_processor_ledgervalue SET
                balance = ledger_value.balance,
                last_modified = ledger_value.last_modified
            WHERE
                id = ledger_value.id;
        ELSE
            INSERT INTO form_processor_ledgervalue (
                case_id, section_id, entry_id, balance, last_modified
            ) VALUES (
                ledger_value.case_id, ledger_value.section_id, ledger_value.entry_id,
                ledger_value.balance, ledger_value.last_modified
            );
        END IF;
    END LOOP;
END
$$ LANGUAGE 'plpgsql';
