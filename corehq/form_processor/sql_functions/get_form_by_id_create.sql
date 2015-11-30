CREATE OR REPLACE FUNCTION get_form_by_id(form_id text) RETURNS form_processor_xforminstancesql AS $$
    SELECT * FROM form_processor_xforminstancesql where form_id = $1;
$$ LANGUAGE SQL;
