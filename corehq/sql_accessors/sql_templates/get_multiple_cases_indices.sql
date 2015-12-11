DROP FUNCTION IF EXISTS get_multiple_cases_indices(TEXT[]);

CREATE FUNCTION get_multiple_cases_indices(case_ids TEXT[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecaseindexsql
    WHERE form_processor_commcarecaseindexsql.case_id = ANY(case_ids);
END;
$$ LANGUAGE plpgsql;
