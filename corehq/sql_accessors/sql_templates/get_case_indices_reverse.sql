DROP FUNCTION IF EXISTS get_case_indices_reverse(text);

CREATE FUNCTION get_case_indices_reverse(case_id text) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    SELECT * FROM form_processor_commcarecaseindexsql
    WHERE form_processor_commcarecaseindexsql.referenced_id = $1;
$$ LANGUAGE SQL;
