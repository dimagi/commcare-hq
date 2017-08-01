DROP FUNCTION IF EXISTS save_ledger_values(TEXT, form_processor_ledgervalue, form_processor_ledgertransaction[], TEXT);

CREATE FUNCTION save_ledger_values(
    case_ids TEXT,
    ledger_value form_processor_ledgervalue,
    ledger_transactions form_processor_ledgertransaction[],
    deprecated_form_id TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    ledger_transaction form_processor_ledgertransaction;
    array_index INT := 1;
BEGIN
    IF ledger_value.id IS NOT NULL THEN
        UPDATE form_processor_ledgervalue SET
            balance = ledger_value.balance,
            last_modified = ledger_value.last_modified,
            daily_consumption = ledger_value.daily_consumption
        WHERE
            id = ledger_value.id;
    ELSE
        INSERT INTO form_processor_ledgervalue (
            case_id, section_id, entry_id, balance, last_modified, last_modified_form_id,
            domain, daily_consumption
        ) VALUES (
            ledger_value.case_id, ledger_value.section_id, ledger_value.entry_id,
            ledger_value.balance, ledger_value.last_modified, ledger_value.last_modified_form_id,
            ledger_value.domain, ledger_value.daily_consumption
        );
    END IF;

    IF deprecated_form_id <> '' THEN
        DELETE FROM form_processor_ledgertransaction
        WHERE
            form_id = deprecated_form_id
            AND case_id = ledger_value.case_id;
    END IF;

    -- insert new transactions
    FOREACH ledger_transaction IN ARRAY ledger_transactions
    LOOP
        IF ledger_transaction.id IS NOT NULL THEN
            UPDATE form_processor_ledgertransaction SET
                delta = ledger_transaction.delta, updated_balance = ledger_transaction.updated_balance
            WHERE
                case_id = ledger_transaction.case_id
                AND section_id = ledger_transaction.section_id
                AND entry_id = ledger_transaction.entry_id
                AND form_id = ledger_transaction.form_id;
        ELSE
            INSERT INTO form_processor_ledgertransaction (
                form_id, server_date, report_date, type, case_id, entry_id, section_id,
                user_defined_type, delta, updated_balance
            ) VALUES (
                ledger_transaction.form_id, ledger_transaction.server_date, ledger_transaction.report_date, ledger_transaction.type,
                ledger_transaction.case_id, ledger_transaction.entry_id, ledger_transaction.section_id,
                ledger_transaction.user_defined_type, ledger_transaction.delta, ledger_transaction.updated_balance
            );
        END IF;
    END LOOP;
END
$$ LANGUAGE 'plpgsql';
