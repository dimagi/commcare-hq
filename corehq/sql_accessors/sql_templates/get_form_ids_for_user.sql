DROP FUNCTION IF EXISTS get_form_ids_for_user(TEXT, TEXT, BOOLEAN);

CREATE FUNCTION get_form_ids_for_user(
    p_domain TEXT,
    p_user_id TEXT,
    is_deleted BOOLEAN) RETURNS TABLE (form_id VARCHAR(255)) AS $$
DECLARE
    deleted_state INT := 0;
BEGIN
    IF is_deleted THEN
        deleted_state := {{ FORM_STATE_DELETED }};
    END IF;

    RETURN QUERY
    SELECT form_processor_xforminstancesql.form_id FROM form_processor_xforminstancesql WHERE
        user_id = p_user_id AND
        domain = p_domain AND
        state & {{ FORM_STATE_DELETED }} = deleted_state;
END;
$$ LANGUAGE plpgsql;
