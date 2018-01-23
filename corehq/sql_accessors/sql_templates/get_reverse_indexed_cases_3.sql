DROP FUNCTION IF EXISTS get_reverse_indexed_cases_3(TEXT, TEXT[]);

CREATE FUNCTION get_reverse_indexed_cases_3(
    domain_name TEXT,
    case_ids TEXT[],
    case_types TEXT[] DEFAULT NULL,
    p_closed BOOLEAN DEFAULT NULL
) RETURNS SETOF form_processor_commcarecasesql AS $$
DECLARE
    query_expr      TEXT := '
    SELECT case_table.* FROM form_processor_commcarecasesql as case_table
        INNER JOIN form_processor_commcarecaseindexsql as case_index_table
            ON ( case_table.case_id = case_index_table.case_id AND case_index_table.domain = $1 )
            JOIN (SELECT UNNEST($2) AS referenced_id) AS cx USING (referenced_id)
    WHERE
        case_table.domain = $1
        AND case_table.deleted = FALSE';
    type_filter     TEXT := ' AND type IN (SELECT * FROM UNNEST($3))';
    closed_filter   TEXT := ' AND closed = $4';
BEGIN
    IF case_types IS NOT NULL THEN
        query_expr := query_expr || type_filter;
    END IF;

    IF p_closed IS NOT NULL THEN
        query_expr := query_expr || closed_filter;
    END IF;

    RETURN QUERY
    EXECUTE query_expr
        USING domain_name, case_ids, case_types, p_closed;
END;
$$ LANGUAGE plpgsql;
