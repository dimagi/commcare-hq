DROP FUNCTION IF EXISTS get_open_cases_by_owners(TEXT, TEXT[], TEXT[]);

CREATE FUNCTION get_open_cases_by_owners(
    domain_name TEXT,
    case_ids_array TEXT[],
    exclude_ids_array TEXT[]
) RETURNS SETOF form_processor_commcarecasesql AS $$
BEGIN
    RETURN QUERY
    WITH case_ids AS (
        SELECT UNNEST(case_ids_array) AS cid
    ), exclude_ids AS (
        SELECT UNNEST(exclude_ids_array) AS xid
    )
    SELECT cases.*
    FROM form_processor_commcarecasesql AS cases
    JOIN (

        -- parent cases
        -- TODO check if this will work with our current sharding scheme
        -- afraid not because referenced_id cases may live in different shard
        -- may need to copy form_processor_commcarecaseindexsql to related shards
        SELECT domain, referenced_id AS case_id
        FROM form_processor_commcarecaseindexsql
        JOIN case_ids ON cid = case_id -- case_id points to child/extension
        WHERE referenced_id NOT IN (SELECT xid FROM exclude_ids)

        UNION

        -- open extension cases
        SELECT domain, case_id
        FROM form_processor_commcarecaseindexsql
        JOIN form_processor_commcarecasesql USING (domain, case_id)
        JOIN case_ids ON cid = referenced_id -- referenced_id points to parent
        WHERE case_id NOT IN (SELECT xid FROM exclude_ids)
            AND relationship_id = 2 -- is extension case
            AND NOT closed
            AND NOT deleted

    ) related USING (domain, case_id)
    WHERE domain = domain_name;
END;
$$ LANGUAGE plpgsql;
