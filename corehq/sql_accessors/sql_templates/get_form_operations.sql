DROP FUNCTION IF EXISTS get_form_operations(TEXT);

CREATE FUNCTION get_form_operations(p_form_id TEXT) RETURNS SETOF form_processor_xformoperationsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xformoperationsql WHERE form_id = p_form_id ORDER BY date ASC;
END;
$$ LANGUAGE plpgsql;
