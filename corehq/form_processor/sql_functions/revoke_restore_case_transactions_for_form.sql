DROP FUNCTION IF EXISTS revoke_restore_case_transactions_for_form(TEXT, BOOLEAN);

CREATE FUNCTION revoke_restore_case_transactions_for_form(form_id TEXT, revoke BOOLEAN) RETURNS void AS $$
BEGIN
    UPDATE form_processor_casetransaction SET revoked=revoke WHERE form_processor_casetransaction.form_id = $1;
END;
$$ LANGUAGE plpgsql;
