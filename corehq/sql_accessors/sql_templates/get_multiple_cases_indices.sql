DROP FUNCTION IF EXISTS get_multiple_cases_indices(text[]);

CREATE FUNCTION get_multiple_cases_indices(case_ids text[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    SELECT * FROM form_processor_commcarecaseindexsql
    WHERE form_processor_commcarecaseindexsql.case_id = ANY($1);
$$ LANGUAGE SQL;
