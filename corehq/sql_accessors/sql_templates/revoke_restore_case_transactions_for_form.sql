DROP FUNCTION IF EXISTS revoke_restore_case_transactions_for_form(TEXT[], TEXT, BOOLEAN);

CREATE FUNCTION revoke_restore_case_transactions_for_form(case_ids TEXT[], p_form_id TEXT, revoke BOOLEAN) RETURNS INTEGER AS $$
DECLARE
    rows_updated INTEGER;
BEGIN
    UPDATE form_processor_casetransaction SET revoked=revoke WHERE form_processor_casetransaction.form_id = p_form_id;
    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    RETURN rows_updated;
END;
$$ LANGUAGE plpgsql;
