DROP FUNCTION IF EXISTS get_reverse_indexed_cases(text, text[]);

CREATE FUNCTION get_reverse_indexed_cases(domain_name text, case_ids text[]) RETURNS SETOF form_processor_commcarecasesql AS $$
    -- TODO exclude case_json
    SELECT form_processor_commcarecasesql.*
--         form_processor_commcarecasesql.id,
--         form_processor_commcarecasesql.case_id,
--         form_processor_commcarecasesql.domain,
--         form_processor_commcarecasesql.type,
--         form_processor_commcarecasesql.name,
--         form_processor_commcarecasesql.owner_id,
--         form_processor_commcarecasesql.opened_on,
--         form_processor_commcarecasesql.opened_by,
--         form_processor_commcarecasesql.modified_on,
--         form_processor_commcarecasesql.server_modified_on,
--         form_processor_commcarecasesql.modified_by,
--         form_processor_commcarecasesql.closed,
--         form_processor_commcarecasesql.closed_on,
--         form_processor_commcarecasesql.closed_by,
--         form_processor_commcarecasesql.deleted,
--         form_processor_commcarecasesql.external_id,
--         form_processor_commcarecasesql.location_id
    FROM form_processor_commcarecasesql
        INNER JOIN form_processor_commcarecaseindexsql
            ON ( form_processor_commcarecasesql.case_id = form_processor_commcarecaseindexsql.case_id )
    WHERE
        form_processor_commcarecasesql.domain = $1
        AND form_processor_commcarecaseindexsql.referenced_id = ANY($2);
$$ LANGUAGE SQL;
