DROP FUNCTION IF EXISTS get_all_ledger_values_modified_since(timestamp with time zone, INTEGER, INTEGER);

CREATE FUNCTION get_all_ledger_values_modified_since(reference_date timestamp with time zone, last_id INTEGER, query_limit integer)
RETURNS SETOF form_processor_ledgervalue AS $$
BEGIN
    RETURN QUERY
    SELECT ledgers.* FROM (
        SELECT * FROM form_processor_ledgervalue
        WHERE last_modified >= reference_date
        LIMIT query_limit + 1
    ) AS ledgers
    WHERE ledgers.id > last_id
    ORDER BY ledgers.last_modified, ledgers.id
    LIMIT query_limit
    ;
END;
$$ LANGUAGE plpgsql;
