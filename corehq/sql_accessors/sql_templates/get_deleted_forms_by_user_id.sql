DROP FUNCTION IF EXISTS get_deleted_forms_by_user_id(TEXT);

CREATE FUNCTION get_deleted_forms_by_user_id(p_user_id TEXT) RETURNS SETOF form_processor_xforminstancesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xforminstancesql WHERE
        user_id = p_user_id AND
        state = {{ deleted_state }};
END;
$$ LANGUAGE plpgsql;

