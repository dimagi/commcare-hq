DROP FUNCTION IF EXISTS get_all_ledger_values_modified_since(timestamp with time zone, integer);

CREATE FUNCTION get_all_ledger_values_modified_since(reference_date timestamp with time zone, query_limit integer)
RETURNS SETOF form_processor_ledgervalue AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_ledgervalue
    WHERE last_modified >= reference_date
    LIMIT query_limit;
END;
$$ LANGUAGE plpgsql;
