DROP FUNCTION IF EXISTS get_case_ids_in_domain(text, text);

CREATE FUNCTION get_case_ids_in_domain(domain_name text, case_type text DEFAULT NULL) RETURNS TABLE (case_id VARCHAR(255)) AS $$
DECLARE
    query_expr  text := 'SELECT case_id FROM form_processor_commcarecasesql WHERE domain = $1';
    type_filter text := ' AND type = $2';
BEGIN
    IF $2 <> '' THEN
        query_expr := query_expr || type_filter;
    END IF;

    RETURN QUERY
    EXECUTE query_expr
        USING $1, $2;
END;
$$ LANGUAGE plpgsql;
