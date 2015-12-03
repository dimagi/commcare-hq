DROP FUNCTION IF EXISTS get_case_form_ids(text);

CREATE FUNCTION get_case_form_ids(case_id text) RETURNS TABLE (form_id VARCHAR(255)) AS $$
DECLARE
    type_form int := 0;
    type_ledger int := 6;
BEGIN
    RETURN QUERY
    SELECT form_processor_casetransaction.form_id FROM form_processor_casetransaction
    WHERE form_processor_casetransaction.case_id = $1
    AND form_processor_casetransaction.revoked = FALSE
    AND form_processor_casetransaction.form_id IS NOT NULL
    AND form_processor_casetransaction.type in (type_form, type_ledger)
    ORDER BY form_processor_casetransaction.server_date;
END;
$$ LANGUAGE plpgsql;
