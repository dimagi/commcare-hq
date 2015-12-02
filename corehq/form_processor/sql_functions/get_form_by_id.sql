DROP FUNCTION IF EXISTS get_form_by_id(form_id text);

CREATE FUNCTION get_form_by_id(form_id text) RETURNS SETOF form_processor_xforminstancesql AS $$
    SELECT * FROM form_processor_xforminstancesql where form_id = $1;
$$ LANGUAGE SQL;
