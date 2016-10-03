DROP FUNCTION IF EXISTS get_all_ledger_values_modified_since(timestamp with time zone, INTEGER, INTEGER);

CREATE FUNCTION get_all_ledger_values_modified_since(reference_date timestamp with time zone, last_id INTEGER, query_limit integer)
RETURNS SETOF form_processor_ledgervalue AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_ledgervalue
        WHERE (last_modified, id) > (reference_date, last_id)
        ORDER BY last_modified, id
        LIMIT query_limit;
END;
$$ LANGUAGE plpgsql;
