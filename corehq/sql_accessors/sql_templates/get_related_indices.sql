DROP FUNCTION IF EXISTS get_related_indices(TEXT, TEXT[], TEXT[]);

CREATE FUNCTION get_related_indices(
    domain_name TEXT,
    case_ids_array TEXT[],
    exclude_indices_array TEXT[]
) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    WITH case_ids AS (
        SELECT UNNEST(case_ids_array) AS cid
    ), exclude_indices AS (
        -- exclude_indices is a set of '<index.case_id> <index.identifier>'
        SELECT UNNEST(exclude_indices_array) AS xid
    )

    -- parent and host cases
    SELECT form_processor_commcarecaseindexsql.*
    FROM form_processor_commcarecaseindexsql
    JOIN case_ids ON cid = case_id -- case_id points to child/extension
    WHERE domain = domain_name
        AND case_id || ' ' || identifier NOT IN (SELECT xid FROM exclude_indices)

    UNION

    -- open extension and child cases
    SELECT DISTINCT form_processor_commcarecaseindexsql.*
    FROM form_processor_commcarecaseindexsql
    JOIN form_processor_commcarecasesql USING (domain, case_id)
    JOIN case_ids ON cid = referenced_id -- referenced_id points to host
    WHERE domain = domain_name
        AND case_id || ' ' || identifier  NOT IN (SELECT xid FROM exclude_indices)
        AND NOT closed
        AND NOT deleted;
END;
$$ LANGUAGE plpgsql;
