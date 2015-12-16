DROP FUNCTION IF EXISTS check_form_exists(TEXT, TEXT);

CREATE FUNCTION check_form_exists(p_form_id TEXT, domain_name TEXT DEFAULT NULL, form_exists OUT BOOLEAN) AS $$
DECLARE
    inner_query   TEXT;
    select_expr   TEXT := 'SELECT 1 FROM form_processor_xforminstancesql WHERE form_id = $1';
    domain_filter TEXT := ' AND domain = $2';
    limit_expr    TEXT := ' LIMIT 1';
    exists        BOOLEAN;
BEGIN
    IF $2 <> '' THEN
        inner_query := select_expr || domain_filter || limit_expr;
    ELSE
        inner_query := select_expr || limit_expr;
    END IF;

    EXECUTE format('SELECT exists(%s)', inner_query)
        INTO form_exists
        USING p_form_id, domain_name;
END;
$$ LANGUAGE plpgsql;
