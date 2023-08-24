DROP FUNCTION IF EXISTS soft_delete_forms_3(TEXT, TEXT[], TIMESTAMP, TEXT);

CREATE FUNCTION soft_delete_forms_3(
    p_domain TEXT,
    form_ids TEXT[],
    p_deletion_date TIMESTAMP,
    p_deletion_id TEXT DEFAULT NULL,
    affected_count OUT INTEGER) AS $$
BEGIN
    UPDATE form_processor_xforminstancesql SET
        deletion_id = p_deletion_id,
        deleted_on = p_deletion_date,
        server_modified_on = p_deletion_date
    WHERE
        domain = p_domain
        AND form_id = ANY(form_ids);
    GET DIAGNOSTICS affected_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
