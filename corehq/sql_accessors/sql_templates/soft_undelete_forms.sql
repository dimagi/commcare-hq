DROP FUNCTION IF EXISTS soft_undelete_forms(TEXT, TEXT[], TEXT);

CREATE FUNCTION soft_undelete_forms(
    p_domain TEXT,
    form_ids TEXT[],
    p_problem TEXT,
    affected_count OUT INTEGER) AS $$
BEGIN
    UPDATE form_processor_xforminstancesql SET
        state = state & ~{{ FORM_STATE_DELETED }},
        problem = p_problem,
        deletion_id = NULL,
        deleted_on = NULL
    WHERE
        domain = p_domain
        AND form_id = ANY(form_ids);
    GET DIAGNOSTICS affected_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
