DROP FUNCTION IF EXISTS get_case_indices_reverse(TEXT, TEXT);

CREATE FUNCTION get_case_indices_reverse(domain_name TEXT, p_case_id TEXT) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    SELECT case_index_table.* FROM form_processor_commcarecaseindexsql as case_index_table
    INNER JOIN form_processor_commcarecasesql AS case_table on case_index_table.case_id = case_table.case_id
    WHERE
        case_table.deleted = False AND
        case_index_table.domain = domain_name
        AND case_index_table.referenced_id = p_case_id;
END;
$$ LANGUAGE plpgsql;
