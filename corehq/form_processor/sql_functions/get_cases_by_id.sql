DROP FUNCTION IF EXISTS get_cases_by_id(text);

CREATE FUNCTION get_cases_by_id(case_ids text[]) RETURNS SETOF form_processor_commcarecasesql AS $$
    SELECT * FROM form_processor_commcarecasesql where case_id = ANY($1);
$$ LANGUAGE SQL;
