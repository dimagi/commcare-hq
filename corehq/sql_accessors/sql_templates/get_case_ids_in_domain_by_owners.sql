DROP FUNCTION IF EXISTS get_case_ids_in_domain_by_owners(text, text[], boolean);

CREATE FUNCTION get_case_ids_in_domain_by_owners(
    domain_name text,
    owner_ids text[],
    p_closed boolean DEFAULT NULL
) RETURNS TABLE (case_id VARCHAR(255)) AS $$
DECLARE
    query_expr TEXT := 'SELECT case_id FROM form_processor_commcarecasesql
            WHERE owner_id = ANY($2)
            AND domain = $1';
    closed_expr TEXT := ' AND closed = $3';
BEGIN
    IF p_closed is NOT NULL THEN
        query_expr := query_expr || closed_expr;
    END IF;

    RETURN QUERY
    EXECUTE query_expr
        USING domain_name, owner_ids, p_closed;
END;
$$ LANGUAGE plpgsql;
