DROP FUNCTION IF EXISTS get_all_cases_modified_since(timestamp with time zone, INTEGER, INTEGER);

CREATE FUNCTION get_all_cases_modified_since(reference_date timestamp with time zone, last_id INTEGER, query_limit integer)
RETURNS SETOF form_processor_commcarecasesql AS $$
BEGIN
    RETURN QUERY
    SELECT cases.* FROM (
        SELECT * FROM form_processor_commcarecasesql as case_table
        WHERE case_table.server_modified_on >= reference_date
        LIMIT query_limit + 1
    ) AS cases
    WHERE cases.id > last_id
    ORDER BY cases.server_modified_on, cases.id
    LIMIT query_limit
    ;
END;
$$ LANGUAGE plpgsql;
