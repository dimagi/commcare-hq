DROP FUNCTION IF EXISTS get_case_indices(TEXT, TEXT);

CREATE FUNCTION get_case_indices(domain_name TEXT, p_case_id TEXT) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecaseindexsql
    WHERE
        form_processor_commcarecaseindexsql.domain = domain_name
        AND form_processor_commcarecaseindexsql.case_id = p_case_id;
END;
$$ LANGUAGE plpgsql;
