DROP FUNCTION IF EXISTS get_ledger_values_for_case(TEXT);

CREATE FUNCTION get_ledger_values_for_case(p_case_id TEXT) RETURNS SETOF form_processor_ledgervalue AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_ledgervalue
    WHERE case_id = p_case_id;
END;
$$ LANGUAGE plpgsql;
