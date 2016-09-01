DROP FUNCTION IF EXISTS get_case_ids_in_domain(TEXT, TEXT, TEXT[], BOOLEAN, BOOLEAN);

CREATE FUNCTION get_case_ids_in_domain(
    domain_name TEXT,
    case_type TEXT DEFAULT NULL,
    owner_ids TEXT[] DEFAULT NULL,
    p_closed BOOLEAN DEFAULT NULL,
    p_deleted BOOLEAN DEFAULT FALSE
) RETURNS TABLE (case_id VARCHAR(255)) AS $$
DECLARE
    query_expr      TEXT := 'SELECT case_id FROM form_processor_commcarecasesql WHERE domain = $1 AND deleted = $2';
    type_filter     TEXT := ' AND type = $3';
    owner_filter    TEXT := ' AND owner_id = ANY($4)';
    closed_filter   TEXT := ' AND closed = $5';
BEGIN
    IF case_type <> '' THEN
        query_expr := query_expr || type_filter;
    END IF;

    IF owner_ids IS NOT NULL AND array_length(owner_ids, 1) > 0 THEN
        query_expr := query_expr || owner_filter;
    END IF;

    IF p_closed IS NOT NULL THEN
        query_expr := query_expr || closed_filter;
    END IF;

    RETURN QUERY
    EXECUTE query_expr
        USING domain_name, p_deleted, case_type, owner_ids, p_closed;
END;
$$ LANGUAGE plpgsql;
