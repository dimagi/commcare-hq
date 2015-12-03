DROP FUNCTION IF EXISTS get_case_by_location_id(text, text);

CREATE FUNCTION get_case_by_location_id(domain_name text, location_id text) RETURNS SETOF form_processor_commcarecasesql AS $$
    SELECT * FROM form_processor_commcarecasesql WHERE domain = $1 AND location_id = $2 AND type = 'supply-point';
$$ LANGUAGE SQL;
