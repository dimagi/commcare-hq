DROP FUNCTION IF EXISTS get_related_indices(TEXT, TEXT[], TEXT[]);

CREATE FUNCTION get_related_indices(
    domain_name TEXT,
    case_ids_array TEXT[],
    exclude_ids_array TEXT[]
) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    WITH case_ids AS (
        SELECT UNNEST(case_ids_array) AS cid
    ), exclude_ids AS (
        SELECT UNNEST(exclude_ids_array) AS xid
    )

    -- parent and host cases
    SELECT form_processor_commcarecaseindexsql.*
    FROM form_processor_commcarecaseindexsql
    JOIN case_ids ON cid = case_id -- case_id points to child/extension
    WHERE domain = domain_name
        AND referenced_id NOT IN (SELECT xid FROM exclude_ids)

    UNION

    -- open extension cases
    SELECT DISTINCT form_processor_commcarecaseindexsql.*
    FROM form_processor_commcarecaseindexsql
    JOIN form_processor_commcarecasesql USING (domain, case_id)
    JOIN case_ids ON cid = referenced_id -- referenced_id points to parent
    WHERE domain = domain_name
        AND case_id NOT IN (SELECT xid FROM exclude_ids)
        AND relationship_id = 2 -- is extension case
        AND NOT closed
        AND NOT deleted;
END;
$$ LANGUAGE plpgsql;
