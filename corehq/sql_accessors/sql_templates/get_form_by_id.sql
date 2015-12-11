DROP FUNCTION IF EXISTS get_form_by_id(TEXT);

CREATE FUNCTION get_form_by_id(p_form_id TEXT) RETURNS SETOF form_processor_xforminstancesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xforminstancesql where form_id = p_form_id;
END;
$$ LANGUAGE plpgsql;
