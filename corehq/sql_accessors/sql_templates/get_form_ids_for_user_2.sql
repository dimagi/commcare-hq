DROP FUNCTION IF EXISTS get_form_ids_for_user_2(TEXT, TEXT, BOOLEAN);

CREATE FUNCTION get_form_ids_for_user_2(
    p_domain TEXT,
    p_user_id TEXT,
    is_deleted BOOLEAN) RETURNS TABLE (form_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT form_processor_xforminstancesql.form_id FROM form_processor_xforminstancesql WHERE
        user_id = p_user_id AND
        domain = p_domain AND
        CASE WHEN is_deleted THEN
            deleted_on IS NOT NULL
        ELSE
            deleted_on IS NULL
        END;
END;
$$ LANGUAGE plpgsql;
