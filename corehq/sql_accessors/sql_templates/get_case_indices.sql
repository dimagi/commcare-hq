DROP FUNCTION IF EXISTS get_case_indices(text);

CREATE FUNCTION get_case_indices(case_id text) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    SELECT * FROM form_processor_commcarecaseindexsql
    WHERE form_processor_commcarecaseindexsql.case_id = $1;
$$ LANGUAGE SQL;
