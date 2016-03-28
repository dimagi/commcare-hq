DROP FUNCTION IF EXISTS get_all_cases_modified_since(timestamp with time zone, integer);

CREATE FUNCTION get_all_cases_modified_since(reference_date timestamp with time zone, query_limit integer)
RETURNS SETOF form_processor_commcarecasesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecasesql as case_table
    WHERE case_table.server_modified_on >= reference_date
    LIMIT query_limit
    ;
END;
$$ LANGUAGE plpgsql;
