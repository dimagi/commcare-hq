DROP FUNCTION IF EXISTS get_ledger_value(TEXT, TEXT, TEXT);

CREATE FUNCTION get_ledger_value(p_case_id TEXT, p_section_id TEXT, p_entry_id TEXT) RETURNS SETOF form_processor_ledgervalue AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_ledgervalue
    WHERE case_id = p_case_id AND section_id = p_section_id AND entry_id = p_entry_id;
END;
$$ LANGUAGE plpgsql;
