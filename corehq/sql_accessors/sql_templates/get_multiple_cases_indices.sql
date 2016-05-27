DROP FUNCTION IF EXISTS get_multiple_cases_indices(TEXT, TEXT[]);

CREATE FUNCTION get_multiple_cases_indices(domain_name TEXT, case_ids TEXT[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecaseindexsql
    WHERE
        form_processor_commcarecaseindexsql.domain = domain_name
        AND form_processor_commcarecaseindexsql.case_id = ANY(case_ids)
    ;
END;
$$ LANGUAGE plpgsql;
