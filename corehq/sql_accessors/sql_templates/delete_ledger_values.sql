DROP FUNCTION IF EXISTS delete_ledger_values(TEXT, TEXT, TEXT);

CREATE FUNCTION delete_ledger_values(
    p_case_id TEXT,
    p_section_id TEXT DEFAULT NULL,
    p_entry_id TEXT DEFAULT NULL,
    deleted_count OUT INTEGER) AS $$
DECLARE
    delete_expr    TEXT := 'DELETE FROM form_processor_ledgervalue WHERE case_id = $1';
    section_filter TEXT := ' AND section_id = $2';
    entry_filter   TEXT := ' AND entry_id = $3';
BEGIN
    IF p_section_id <> '' THEN
        delete_expr := delete_expr || section_filter;
    END IF;

    IF p_entry_id <> '' THEN
        delete_expr := delete_expr || entry_filter;
    END IF;

    EXECUTE delete_expr
        USING p_case_id, p_section_id, p_entry_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
