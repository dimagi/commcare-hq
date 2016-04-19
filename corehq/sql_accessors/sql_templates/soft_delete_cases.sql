DROP FUNCTION IF EXISTS soft_delete_cases(TEXT, TEXT[], TIMESTAMP, TIMESTAMP, TEXT);

CREATE FUNCTION soft_delete_cases(
    p_domain TEXT,
    case_ids TEXT[],
    p_server_modified_on TIMESTAMP,
    p_deletion_date TIMESTAMP,
    p_deletion_id TEXT DEFAULT NULL,
    affected_count OUT INTEGER) AS $$
BEGIN
    UPDATE form_processor_commcarecasesql SET
        deleted = TRUE,
        server_modified_on = p_server_modified_on,
        deletion_id = p_deletion_id,
        deleted_on = p_deletion_date
    WHERE
        domain = p_domain
        AND case_id = ANY(case_ids);
    GET DIAGNOSTICS affected_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
