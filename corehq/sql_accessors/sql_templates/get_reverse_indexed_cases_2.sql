DROP FUNCTION IF EXISTS get_reverse_indexed_cases(TEXT, TEXT[]);

CREATE FUNCTION get_reverse_indexed_cases(domain_name TEXT, case_ids TEXT[]) RETURNS SETOF form_processor_commcarecasesql AS $$
BEGIN
    RETURN QUERY
    SELECT case_table.* FROM form_processor_commcarecasesql as case_table
        INNER JOIN form_processor_commcarecaseindexsql as case_index_table
            ON ( case_table.case_id = case_index_table.case_id AND case_index_table.domain = domain_name )
    WHERE
        case_table.domain = domain_name
        AND case_table.deleted = FALSE
        AND case_index_table.referenced_id = ANY(case_ids);
END;
$$ LANGUAGE plpgsql;

