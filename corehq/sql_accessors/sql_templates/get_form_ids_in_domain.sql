DROP FUNCTION IF EXISTS get_form_ids_in_domain(text, text);

CREATE FUNCTION get_form_ids_in_domain(domain_name text, user_id text) RETURNS TABLE (form_id VARCHAR(255)) AS $$
DECLARE
    query_expr  text := 'SELECT form_id FROM form_processor_xforminstancesql WHERE domain = $1';
    type_filter text := ' AND user_id = $2';
BEGIN
    IF $2 <> '' THEN
        query_expr := query_expr || type_filter;
    END IF;

    RETURN QUERY
    EXECUTE query_expr
        USING $1, $2;
END;
$$ LANGUAGE plpgsql;
