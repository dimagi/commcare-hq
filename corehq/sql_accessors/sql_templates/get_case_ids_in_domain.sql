DROP FUNCTION IF EXISTS get_case_ids_in_domain(TEXT, TEXT);

CREATE FUNCTION get_case_ids_in_domain(domain_name TEXT, case_type TEXT DEFAULT NULL) RETURNS TABLE (case_id VARCHAR(255)) AS $$
DECLARE
    query_expr  TEXT := 'SELECT case_id FROM form_processor_commcarecasesql WHERE domain = $1';
    type_filter TEXT := ' AND type = $2';
BEGIN
    IF $2 <> '' THEN
        query_expr := query_expr || type_filter;
    END IF;

    RETURN QUERY
    EXECUTE query_expr
        USING domain_name, case_type;
END;
$$ LANGUAGE plpgsql;
