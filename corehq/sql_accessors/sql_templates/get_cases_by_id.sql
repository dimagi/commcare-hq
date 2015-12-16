DROP FUNCTION IF EXISTS get_cases_by_id(TEXT[]);

CREATE FUNCTION get_cases_by_id(case_ids TEXT[]) RETURNS SETOF form_processor_commcarecasesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecasesql where case_id = ANY(case_ids);
END;
$$ LANGUAGE plpgsql;
