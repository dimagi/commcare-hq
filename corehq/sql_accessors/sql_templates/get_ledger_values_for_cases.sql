DROP FUNCTION IF EXISTS get_ledger_values_for_cases(TEXT[]);

CREATE FUNCTION get_ledger_values_for_cases(p_case_ids TEXT[]) RETURNS SETOF form_processor_ledgervalue AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_ledgervalue
    WHERE case_id = ANY(p_case_ids);
END;
$$ LANGUAGE plpgsql;
