DROP FUNCTION IF EXISTS get_form_operations(form_id text);

CREATE FUNCTION get_form_operations(form_id text) RETURNS SETOF form_processor_xformoperationsql AS $$
    SELECT * FROM form_processor_xformoperationsql WHERE form_id = $1 ORDER BY date ASC;
$$ LANGUAGE SQL;
