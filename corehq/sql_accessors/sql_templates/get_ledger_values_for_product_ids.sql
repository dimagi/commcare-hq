-- drop it first in case we're changing the signature in which case 'CREATE OR REPLACE' will fail
DROP FUNCTION IF EXISTS get_ledger_values_for_product_ids(TEXT[]);

-- return SETOF so that we get 0 rows when no form matches otherwise we'll get an empty row
CREATE FUNCTION get_ledger_values_for_product_ids(p_product_ids TEXT[]) RETURNS SETOF form_processor_ledgervalue AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_ledgervalue WHERE
        entry_id = ANY(p_product_ids);
END;
$$ LANGUAGE plpgsql;
