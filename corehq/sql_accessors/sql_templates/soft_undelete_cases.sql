DROP FUNCTION IF EXISTS soft_undelete_cases(TEXT, TEXT[]);

CREATE FUNCTION soft_undelete_cases(
    p_domain TEXT,
    case_ids TEXT[],
    affected_count OUT INTEGER) AS $$
BEGIN
    UPDATE form_processor_commcarecasesql SET
        deleted = FALSE,
        server_modified_on = p_server_modified_on,
        deletion_id = NULL,
        deleted_on = NULL
    WHERE
        domain = p_domain
        AND case_id = ANY(case_ids);
    GET DIAGNOSTICS affected_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
