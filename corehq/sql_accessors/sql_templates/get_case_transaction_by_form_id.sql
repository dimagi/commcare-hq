DROP FUNCTION IF EXISTS get_case_transaction_by_form_id(TEXT, TEXT);

CREATE FUNCTION get_case_transaction_by_form_id(p_case_id TEXT, p_form_id TEXT) RETURNS SETOF form_processor_casetransaction AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_casetransaction
    WHERE form_id = p_form_id AND case_id = p_case_id;
END;
$$ LANGUAGE plpgsql;
