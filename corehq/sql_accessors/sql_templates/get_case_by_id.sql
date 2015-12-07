DROP FUNCTION IF EXISTS get_case_by_id(text);

CREATE FUNCTION get_case_by_id(case_id text) RETURNS SETOF form_processor_commcarecasesql AS $$
    SELECT * FROM form_processor_commcarecasesql where case_id = $1;
$$ LANGUAGE SQL;
