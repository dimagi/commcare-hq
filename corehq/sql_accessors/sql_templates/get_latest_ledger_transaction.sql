DROP FUNCTION IF EXISTS get_latest_ledger_transaction(TEXT, TEXT, TEXT);

CREATE FUNCTION get_latest_ledger_transaction(
    p_case_id TEXT, p_section_id TEXT, p_entry_id TEXT
) RETURNS SETOF form_processor_ledgertransaction AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_ledgertransaction
    WHERE case_id = p_case_id AND section_id = p_section_id AND entry_id = p_entry_id
    ORDER BY report_date DESC, "id" DESC limit 1;
END;
$$ LANGUAGE plpgsql;
