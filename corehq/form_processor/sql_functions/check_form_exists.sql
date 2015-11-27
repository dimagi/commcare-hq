DROP FUNCTION IF EXISTS check_form_exists(text, text);

CREATE FUNCTION check_form_exists(form_id text, domain_name text DEFAULT NULL) RETURNS BOOLEAN AS $$
DECLARE
    inner_query   text;
    select_expr   text := 'SELECT 1 FROM form_processor_xforminstancesql WHERE form_id = $1';
    domain_filter text := ' AND domain = $2';
    limit_expr    text := ' LIMIT 1';
    exists        boolean;
BEGIN
    IF domain_name <> '' THEN
        inner_query := select_expr || domain_filter || limit_expr;
    ELSE
        inner_query := select_expr || limit_expr;
    END IF;

    RAISE NOTICE 'running query select exists(%s)', inner_query;
    EXECUTE format('SELECT exists(%s)', inner_query)
        INTO exists
        USING form_id, domain_name;
    RETURN exists;
END;
$$ LANGUAGE plpgsql;
