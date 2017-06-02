DROP FUNCTION IF EXISTS get_open_cases_by_owners(TEXT, TEXT[]);

CREATE FUNCTION get_open_cases_by_owners(
    domain_name TEXT,
    owner_ids_array TEXT[]
) RETURNS SETOF form_processor_commcarecasesql AS $$
BEGIN
    RETURN QUERY
    WITH owner_ids AS (
        SELECT UNNEST(owner_ids_array) AS id
    )
    SELECT cases.* FROM form_processor_commcarecasesql AS cases
    LEFT JOIN form_processor_commcarecaseindexsql AS case_index
        ON cases.domain = case_index.domain AND cases.case_id = case_index.case_id
    WHERE cases.domain = domain_name
        AND owner_id IN (SELECT id FROM owner_ids)
        AND NOT closed
        AND NOT deleted
        AND (
            -- exclude extension cases
            case_index.case_id IS NULL OR case_index.relationship_id != 2
        );
END;
$$ LANGUAGE plpgsql;
