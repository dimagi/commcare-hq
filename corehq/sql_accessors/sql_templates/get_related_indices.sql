DROP FUNCTION IF EXISTS get_related_indices(TEXT, TEXT[], TEXT[]);

CREATE FUNCTION get_related_indices(
    domain_name TEXT,
    case_ids_array TEXT[],
    exclude_indices_array TEXT[]
) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    CREATE TEMP TABLE case_ids ON COMMIT DROP AS
        SELECT UNNEST(case_ids_array) AS cid;

    CREATE TEMP TABLE exclude_indices ON COMMIT DROP AS
        -- exclude_indices is a set of '<index.case_id> <index.identifier>'
        SELECT UNNEST(exclude_indices_array) AS xid;

    CREATE UNIQUE INDEX ON case_ids (cid);
    CREATE UNIQUE INDEX ON exclude_indices (xid);

    RETURN QUERY

    -- parent and host cases
    SELECT form_processor_commcarecaseindexsql.*
    FROM form_processor_commcarecaseindexsql
    JOIN case_ids ON cid = case_id -- case_id points to child/extension
    LEFT JOIN exclude_indices ON xid = case_id || ' ' || identifier
    WHERE domain = domain_name AND xid IS NULL

    UNION

    -- open extension cases
    SELECT DISTINCT form_processor_commcarecaseindexsql.*
    FROM form_processor_commcarecaseindexsql
    JOIN form_processor_commcarecasesql USING (domain, case_id)
    JOIN case_ids ON cid = referenced_id -- referenced_id points to host
    LEFT JOIN exclude_indices ON xid = case_id || ' ' || identifier
    WHERE domain = domain_name
        AND xid IS NULL
        AND relationship_id = 2 -- is extension case
        AND NOT closed
        AND NOT deleted;
END;
$$ LANGUAGE plpgsql;
