DROP FUNCTION IF EXISTS get_case_transactions_by_type(TEXT, INTEGER);

CREATE FUNCTION get_case_transactions_by_type(p_case_id TEXT, p_transaction_type INTEGER) RETURNS SETOF form_processor_casetransaction AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_casetransaction
    WHERE form_processor_casetransaction.case_id = p_case_id
    AND form_processor_casetransaction.revoked = FALSE
    AND form_processor_casetransaction.type & p_transaction_type = p_transaction_type
    ORDER BY form_processor_casetransaction.server_date;
END;
$$ LANGUAGE plpgsql;

