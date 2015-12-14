DROP FUNCTION IF EXISTS get_case_transactions(TEXT);

CREATE FUNCTION get_case_transactions(p_case_id TEXT) RETURNS SETOF form_processor_casetransaction AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_casetransaction where case_id = p_case_id ORDER BY server_date;
END;
$$ LANGUAGE plpgsql;
