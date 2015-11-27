DROP FUNCTION IF EXISTS revoke_case_transactions_for_form(text, text);

CREATE FUNCTION revoke_case_transactions_for_form(form_id text) RETURNS void AS $$
BEGIN
    UPDATE form_processor_casetransaction SET revoked=TRUE WHERE form_processor_casetransaction.form_id = $1;
END;
$$ LANGUAGE plpgsql;

