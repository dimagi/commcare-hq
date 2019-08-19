DROP FUNCTION IF EXISTS get_ledger_values_for_cases_2(TEXT[], TEXT[], TEXT[], TIMESTAMP, TIMESTAMP);

CREATE FUNCTION get_ledger_values_for_cases_2(
    p_case_ids TEXT[],
    p_section_ids TEXT[] DEFAULT NULL,
    p_entry_ids TEXT[] DEFAULT NULL,
    date_window_start TIMESTAMP DEFAULT NULL,
    date_window_end TIMESTAMP DEFAULT NULL
) RETURNS SETOF form_processor_ledgervalue AS $$
DECLARE
    select_expr         TEXT := 'SELECT * FROM form_processor_ledgervalue WHERE case_id = ANY($1)';
    section_filter TEXT := ' AND section_ids = ANY($2)';
    entry_filter   TEXT := ' AND entry_ids = ANY($3)';
    date_filter_start   TEXT := ' AND last_modified >= $4';
    date_filter_end     TEXT := ' AND last_modified <= $5';
BEGIN
    IF p_section_ids <> '' THEN
        select_expr := select_expr || section_filter;
    END IF;

    IF p_entry_ids <> '' THEN
        select_expr := select_expr || entry_filter;
    END IF;

    IF date_window_start IS NOT NULL THEN
        select_expr := select_expr || date_filter_start;
    END IF;

    IF date_window_end IS NOT NULL THEN
        select_expr := select_expr || date_filter_end;
    END IF;

    RETURN QUERY
    EXECUTE select_expr
        USING p_case_ids, p_section_ids, p_entry_ids, date_window_start, date_window_end;
END;
$$ LANGUAGE plpgsql;
