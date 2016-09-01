DROP FUNCTION IF EXISTS get_case_by_external_id(TEXT, TEXT, TEXT);

CREATE FUNCTION get_case_by_external_id(p_domain TEXT, p_external_id TEXT, p_type TEXT DEFAULT NULL) RETURNS SETOF form_processor_commcarecasesql AS $$
DECLARE
    query_expr    TEXT := 'SELECT * FROM form_processor_commcarecasesql WHERE domain = $1 AND external_id = $2 AND deleted = FALSE';
    type_filter   TEXT := ' AND type = $3';
BEGIN
    IF p_type <> '' THEN
        query_expr := query_expr || type_filter;
    END IF;

    RETURN QUERY
    EXECUTE query_expr
        USING p_domain, p_external_id, p_type;
END;
$$ LANGUAGE plpgsql;
