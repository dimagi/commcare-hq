DROP FUNCTION IF EXISTS get_case_transactions_for_rebuild(TEXT);

CREATE FUNCTION get_case_transactions_for_rebuild(p_case_id TEXT) RETURNS SETOF form_processor_casetransaction AS $$
DECLARE
    type_form INTEGER := {{ TRANSACTION_TYPE_FORM }};
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_casetransaction
    WHERE form_processor_casetransaction.case_id = p_case_id
    AND form_processor_casetransaction.revoked = FALSE
    AND form_processor_casetransaction.form_id IS NOT NULL
    AND form_processor_casetransaction.type = type_form
    ORDER BY form_processor_casetransaction.server_date;
END;
$$ LANGUAGE plpgsql;
