DROP FUNCTION IF EXISTS get_case_by_id(TEXT);

CREATE FUNCTION get_case_by_id(p_case_id TEXT) RETURNS SETOF form_processor_commcarecasesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecasesql where case_id = p_case_id;
END;
$$ LANGUAGE plpgsql;
