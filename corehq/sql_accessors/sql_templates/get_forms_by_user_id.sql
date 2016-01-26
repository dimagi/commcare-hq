DROP FUNCTION IF EXISTS get_forms_by_user_id(TEXT, TEXT, INTEGER);

CREATE FUNCTION get_forms_by_user_id(p_domain TEXT, p_user_id TEXT, p_state INTEGER) RETURNS SETOF form_processor_xforminstancesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xforminstancesql WHERE
        user_id = p_user_id AND
        domain = p_domain AND
        state = p_state
END;
$$ LANGUAGE plpgsql;
