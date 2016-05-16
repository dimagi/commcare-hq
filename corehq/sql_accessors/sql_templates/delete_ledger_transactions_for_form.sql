DROP FUNCTION IF EXISTS delete_ledger_transactions_for_form(TEXT[], TEXT);

CREATE FUNCTION delete_ledger_transactions_for_form(case_ids TEXT[], p_form_id TEXT, deleted_count OUT INTEGER) AS $$
BEGIN
    DELETE FROM form_processor_ledgertransaction WHERE form_id = p_form_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
