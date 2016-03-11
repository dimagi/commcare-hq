DROP FUNCTION IF EXISTS get_ledger_transactions_for_case(TEXT, TEXT, TEXT, TIMESTAMP, TIMESTAMP);

CREATE FUNCTION get_ledger_transactions_for_case(
    p_case_id TEXT,
    p_entry_id TEXT DEFAULT NULL,
    p_section_id TEXT DEFAULT NULL,
    date_window_start TIMESTAMP DEFAULT NULL,
    date_window_end TIMESTAMP DEFAULT NULL
) RETURNS SETOF form_processor_ledgertransaction AS $$
DECLARE
    select_expr    TEXT := 'SELECT * FROM form_processor_ledgertransaction WHERE case_id = $1';
    entry_filter   TEXT := ' AND entry_id = $2';
    section_filter TEXT := ' AND section_id = $3';
    date_filter    TEXT := ' AND server_date > $4 AND server_date <= %5';
    exists        BOOLEAN;
BEGIN
    IF p_entry_id <> '' THEN
        select_expr := select_expr || entry_filter;
    END IF;

    IF p_section_id <> '' THEN
        select_expr := select_expr || section_filter;
    END IF;

    IF date_window_start IS NOT NULL AND date_window_end IS NOT NULL THEN
        select_expr := select_expr || date_filter;
    END IF;

    select_expr := select_expr || ' ORDER BY server_date';

    RETURN QUERY
    EXECUTE select_expr
        USING p_case_id, p_entry_id, p_section_id, date_window_start, date_window_end;
END;
$$ LANGUAGE plpgsql;
