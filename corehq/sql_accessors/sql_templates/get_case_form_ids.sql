DROP FUNCTION IF EXISTS get_case_form_ids(TEXT);

CREATE FUNCTION get_case_form_ids(p_case_id TEXT) RETURNS TABLE (form_id VARCHAR(255)) AS $$
DECLARE
    type_form INTEGER := {{ TRANSACTION_TYPE_FORM }};
    type_ledger INTEGER := {{ TRANSACTION_TYPE_LEDGER }};
BEGIN
    RETURN QUERY
    SELECT transactions.form_id FROM (
        SELECT
            DISTINCT on (form_id) form_processor_casetransaction.form_id,
            form_processor_casetransaction.server_date
        FROM form_processor_casetransaction
        WHERE form_processor_casetransaction.case_id = p_case_id
        AND form_processor_casetransaction.revoked = FALSE
        AND form_processor_casetransaction.form_id IS NOT NULL
        AND ((form_processor_casetransaction.type & type_form) = type_form
        OR form_processor_casetransaction.type = type_ledger)
    ) transactions
    ORDER BY transactions.server_date;
END;
$$ LANGUAGE plpgsql;
